from flask import Flask, render_template
from bs4 import BeautifulSoup
import requests
import time
from random import randint
import ibm_watson
from ibm_watson import NaturalLanguageUnderstandingV1
from ibm_watson.natural_language_understanding_v1 \
  import Features, EntitiesOptions, KeywordsOptions, SemanticRolesOptions, SentimentOptions, EmotionOptions, ConceptsOptions, CategoriesOptions

import json
import sys
import time
import ast
import os

import operator
from functools import reduce
from io import StringIO
import numpy as np
from os.path import join, dirname
import requests
import re
import nltk
from nltk import word_tokenize,sent_tokenize,ne_chunk


app = Flask(__name__)

natural_language_understanding = NaturalLanguageUnderstandingV1(
    version='2018-08-14',
    )

@app.route("/")
def indexpage():
    news_details=dict()
    result = '{"name":"Bank EWS","children":[{"name":"Management Default","children":[]},{"name":"Management Change","children":[]},{"name":"Credit Rating","children":[]},{"name":"Financial Analysis","children":[]},{"name":"Capital Adequacy","children":[]},{"name":"Legal Action","children":[]},{"name":"Strike","children":[]},{"name":"Loan Servicing","children":[]},{"name":"Share Price Deviation","children":[]},{"name":"Auditors Change","children":[]},{"name":"Terminal Disablement","children":[]},{"name":"Security Related","children":[]}]}'

    config_file = open("config.json","r")
    config = config_file.read()

    news_details,rel=discover_news_related_entities('director resign','Management Change',news_details,result, config, 'NO','NO')
    news_details,rel=discover_news_related_entities('loan default','Management Default',news_details,result, config, 'NO','NO')
    news_details,rel=discover_news_related_entities('rating downgrade','Credit Rating',news_details,json.dumps(rel), config, 'NO','NO')
    news_details,rel=discover_news_related_entities('worker or employee strike','Strike',news_details,json.dumps(rel), config, 'NO','NO')
    news_details,rel=discover_news_related_entities('stocks news','Share Price Deviation',news_details,json.dumps(rel), config, 'NO','NO')

    #msg=(open("client_network.json","r")).read()
    #msg=ast.literal_eval(msg)
    #print(msg['children'])
    client_network_list= extract_client_info(rel)
    return render_template("client_network_banking.html", news_details = news_details, client_details= client_network_list)


def DisplayHtml(htmlText):
    htmlTxt = HTML(htmlText)
    display(htmlTxt)


def scrape_news_summaries(s):
    time.sleep(randint(0, 2))  # relax and don't let google be angry
    r = requests.get("https://www.google.co.in/search?q="+s+"&num=100&cr=countryIN&dcr=0&source=lnms&tbm=nws&sa=X&ved=0ahUKEwim2-36-OfXAhVIs48KHX1fABsQ_AUICygC&biw=1280&bih=623")
    print(r.status_code)  # Print the status code
    content = r.text
    news_summaries = []
    news_links = []
    soup = BeautifulSoup(content, "html.parser")
    for item in soup.find_all('h3',{'class':'r'}):
          for post in item.find_all('a'):
                news_summaries.append(post.text)
                news_links.append(post)
    return news_summaries,news_links

def scrape_stocknews_summaries(s):
    time.sleep(randint(0, 2))  # relax and don't let google be angry
    r = requests.get("https://www.indiainfoline.com/top-news")
    print(r.status_code)  # Print the status code
    content = r.text
    news_summaries = []
    news_links = []
    soup = BeautifulSoup(content, "html.parser")
    for item in soup.find_all('p',{'class':'heading'}):
          for post in item.find_all('a'):
                news_summaries.append(post.text)
                news_links.append(post)
    return news_summaries,news_links


def discover_news_related_entities(searchterm,eventType,res,Eventsjson,configjson,refeshValue,verboseFlag):
    
    """ Extract news from popular websites
    """        
    news_file_name = "newsfile_"+eventType+".txt"
    news_entity_file_name = "newsentityfile_"+eventType+".txt"
    news_link_file_name = "newslinkfile_"+eventType+".txt"

    newsfile = open(news_file_name,"w") 
    linkfile = open(news_link_file_name,"w") 

    if(eventType == 'Share Price Deviation'):
        l = scrape_stocknews_summaries(searchterm)
    else:
        l = scrape_news_summaries(searchterm)
    res[eventType]= dict(zip(l[0],l[1]))

    for n in l[0]:
        regexstr = '[ ][\.][\.][\.]'
        cleantext = re.sub(regexstr,'',n)
        newsfile.write(cleantext+'\n')
    newsfile.close() 

    for m in l[1]:
        linkfile.write(str(m)+'\n')
    linkfile.close() 

    """ Find entities in news items
    """            
    news_file = open(news_file_name,"r")
    news_entity_file = open(news_entity_file_name,"w") 

    newsText = news_file.read()
    '''print ('============= NEWS TEXT===============')
    print(newsText)
    print ('======================================')'''

    nluresponse = analyze_using_NLU(newsText)
    '''print ('==============NLU RESPONSE==============')        
    print(nluresponse)
    print ('=========================================')'''

    #print ('==============ENTITY TEXT==============')               
    disambiguated_text = disambiguate_entities(newsText,nluresponse,configjson,verboseFlag)
    #print(disambiguated_text)
    #print ('=========================================')        
    news_entity_file.write(disambiguated_text)

    news_file.close()
    news_entity_file.close()


    """ Find events and its related entities in news items
    """ 
    news_file = open(news_file_name,"r")
    newsText = news_file.read()
    relationships=[]
    
    disambiguated_entity_file = open(news_entity_file_name,"r") 
    entityText = disambiguated_entity_file.read()
    
    links_file = open(news_link_file_name,"r")
    linksText = links_file.read()
        
    resultjson = json.loads(Eventsjson)

    relationships = extract_event_related_entities(eventType,newsText,entityText,linksText,configjson,resultjson,verboseFlag)

    return  res,relationships
    

def extract_event_related_entities(evtType,newstext,entitytext,linkstext,config,relations,verboseValue):
    """ Extract entity relationships in a sentence
    """    
    sentenceList = split_sentences(entitytext)
    newsList = split_sentences(newstext)     
    nlinkList = split_sentences(linkstext)    
    configjson = json.loads(config)
    for event_type in relations['children']:
          if event_type['name'] == evtType:
            event_List = event_type['children']
    
    
    for indx,sentences in enumerate(sentenceList):
        if verboseValue == 'YES':
            print ('>> '+sentences+' <<')
        for rules in configjson['configuration']['relations']['rules']:

            if (rules['type'] == 'd_regex'):
                for regex in rules['d_regex']:
                    if ('event' in regex) and (regex['event'] == evtType):
                        if verboseValue == 'YES':
                            print ('EVENT REGEX:',regex)
                        regextags = regex_tagging(regex['tag'],regex['pattern'],sentences)
                        if verboseValue == 'YES':
                            print(regextags)
                        if (len(regextags)>0):
                            if verboseValue == 'YES':
                                print("EVENT")
                                print("INDEX",indx)
                                print("NEWS ITEM",newsList[indx])
                                print("LINK",nlinkList[indx])                                
                        for events in regextags:
                            if verboseValue == 'YES':
                                print(events)
                           
                        newEvent = {"name": newsList[indx],"children": [ ],"sentence":sentences,"newslink":nlinkList[indx],"status": ''}                                                                  
                        if verboseValue == 'YES':
                            print("EVENT JSON:",newEvent)
                        event_List.append(newEvent)
                        for entity in regex['related_entity']:
                            if (entity['type'] == 'd_regex'):
                                if verboseValue == 'YES':
                                    print(entity['pattern'])
                                entitytags = regex_tagging(entity['tag'],entity['pattern'],sentences)
                                if (len(entitytags)>0):
                                    if verboseValue == 'YES':
                                        print("ENTITY")
                                    for words in entitytags:
                                        newEntity = {"name": words,"status": entity['status']}
                                        event_List[-1]['children'].append(newEntity)
                                        if(entity['status']=='Verified'):
                                            event_List[-1]['status']= entity['status']
                                        if verboseValue == 'YES':
                                            print(event_List[0])


    if verboseValue == 'YES':
        print(relations)
        
    return relations

def disambiguate_entities(text,NLUresponse,config,verboseValue):
    """ Resolve disambiguity in the text using entities and entity resolution performed using Watson NLU
    """  
    name_tagged_text = []
    taggedtext = text
    configjson = json.loads(config)

    sentenceList = split_sentences(taggedtext)
    for sentences in sentenceList:
        tokens = split_into_tokens(sentences)
        postags = POS_tagging(tokens)
        if verboseValue == 'YES':
            print(postags)
        name_list = chunk_tagging('NAME','NAME:{<NNP>+}',postags)
        for names in name_list:
            if verboseValue == 'YES':
                print('Adding NAME-',names)
            name_tagged_text.append(names)

    if verboseValue == 'YES':
        print('NAMES :',name_tagged_text)
            
    if (NLUresponse == ''):
        if verboseValue == 'YES':
            print('NO JSON')
        response = analyze_using_NLU(text)
    else:
        if verboseValue == 'YES':
            print('YES JSON')
        response = NLUresponse

    responsejson = json.loads(str(response['results']))
    
        
    for stages in configjson['configuration']['classification']['stages']:
        if verboseValue == 'YES':
            print('Stage - Performing ' + stages['name']+':')
        for steps in stages['steps']:
            if verboseValue == 'YES':
                print('    Step - ' + steps['type']+':')
            if (steps['type'] == 'keywords'):
                for keyword in steps['keywords']:
                    for word in sentenceList:
                        wordtag = keyword_tagging(keyword['tag'],keyword['text'],word)
                        if(wordtag != 'UNKNOWN'):
                            if verboseValue == 'YES':
                                print('      '+keyword['tag']+':'+wordtag)
                            augument_NLUResponse(responsejson,'entities',wordtag,keyword['tag'])
            elif(steps['type'] == 'd_regex'):
                for regex in steps['d_regex']:
                    for word in sentenceList:
                        regextags = regex_tagging(regex['tag'],regex['pattern'],word)
                        if (len(regextags)>0):
                            for words in regextags:
                                if verboseValue == 'YES':
                                    print('      '+regex['tag']+':'+words)
                                augument_NLUResponse(responsejson,'entities',words,regex['tag'])
            elif(steps['type'] == 'chunking'):
                for chunk in steps['chunk']:
                    chunktags = chunk_tagging(chunk['tag'],chunk['pattern'],postags)
                    if (len(chunktags)>0):
                        for words in chunktags:
                            if verboseValue == 'YES':
                                print('      '+chunk['tag']+':'+words)
                            augument_NLUResponse(responsejson,'entities',words,chunk['tag'])
                            
            else:
                if verboseValue == 'YES':
                    print('UNKNOWN STEP')
                  
    for entities in responsejson['result']['entities']:
        entities['text']=entities['text'].replace(")","")
        regexstr = entities['text']+'(?!>)'
        print(entities['text'], regexstr)
        taggedtext = re.sub(regexstr,'<'+entities['type']+':'+entities['text']+'>',taggedtext)
    
    for roles in responsejson['result']['semantic_roles']:
        if 'entities' not in roles['subject']:
            if verboseValue == 'YES':
                print('NO ENTITY')
        else:
            for entity in roles['subject']['entities']:
                if 'disambiguation' not in entity:
                    if verboseValue == 'YES':
                        print('NO DISAMBIGUATION')
                else:
                    regexstr = roles['subject']['text']+'(?!>)'
                    regex = re.compile(regexstr, re.IGNORECASE)
                    taggedtext = re.sub(regexstr,'<'+entity['type']+':'+entity['text']+'>',taggedtext)
 
    for name in name_tagged_text:
        regexstr = name+'(?!>)'
        regex = re.compile(regexstr, re.IGNORECASE) 
        taggedtext = re.sub(regexstr,'<NAME:'+name+'>',taggedtext)
        
    if verboseValue == 'YES':
        print(taggedtext)
    return taggedtext

def split_sentences(text):
    """ Split text into sentences.
    """
    sentence_delimiters = re.compile(u'[\n]')
    sentences = sentence_delimiters.split(text)
    return sentences

def split_into_tokens(text):
    """ Split text into tokens.
    """
    tokens = nltk.word_tokenize(text)
    return tokens

def POS_tagging(text):
    """ Generate Part of speech tagging of the text.
    """
    POSofText = nltk.tag.pos_tag(text)
    return POSofText

def chunk_tagging(tag,chunk,text):
    """ Tag the text using chunking.
    """
    parsed_cp = nltk.RegexpParser(chunk)
    pos_cp = parsed_cp.parse(text)
    chunk_list=[]
    for root in pos_cp:
        if isinstance(root, nltk.tree.Tree):               
            if root.label() == tag:
                chunk_word = ''
                for child_root in root:
                    chunk_word = chunk_word +' '+ child_root[0]
                chunk_list.append(chunk_word)
    return chunk_list

def keyword_tagging(tag,tagtext,text):
    """ Tag the text matching keywords.
    """
    if (text.lower().find(tagtext.lower()) != -1):
        return text[text.lower().find(tagtext.lower()):text.lower().find(tagtext.lower())+len(tagtext)]
    else:
        return 'UNKNOWN'
    
def augument_NLUResponse(responsejson,updateType,text,tag):
    """ Update the NLU response JSON with augumented classifications.
    """
    if(updateType == 'keyword'):
        if not any(d.get('text', None) == text for d in responsejson['result']['keywords']):
            responsejson['keywords'].append({"text":text,"relevance":0.5})
    else:
        print('-----response-----')
        print(responsejson)
        if not any(d.get('text', None) == text for d in responsejson['result']['entities']):
            responsejson['result']['entities'].append({"type":tag,"text":text,"relevance":0.5,"count":1})    
            
def regex_tagging(tag,regex,text):
    """ Tag the text matching REGEX.
    """    
    p = re.compile(regex, re.IGNORECASE)
    matchtext = p.findall(text)
    regex_list=[]    
    if (len(matchtext)>0):
        for regword in matchtext:
            regex_list.append(regword)
    return regex_list




def analyze_using_NLU(analysistext):
    """ Extract results from Watson Natural Language Understanding for each news item
    """
    res=dict()
    response = natural_language_understanding.analyze( 
        text=analysistext,
        features=Features(
                          sentiment=SentimentOptions(),
                          entities=EntitiesOptions(), 
                          keywords=KeywordsOptions(),
                          emotion=EmotionOptions(),
                          concepts=ConceptsOptions(),
                          categories=CategoriesOptions(),
                          semantic_roles=SemanticRolesOptions()))
    res['results']=response
    return res


def extract_client_info(msg):
    """ Builds json to send to the HTML page
    """
    client_network_list=list()
    for m in msg['children']:
        for k,v in m.items():
            '''print(m['name'])
            print("-------------------------------------------")'''
            for x in m['children']:
                client_network=dict()
                client_network['Event_Type']=m['name']
                #print(x['newslink'])
                if  "<a" in x['newslink']:
                    if (client_network['Event_Type'] != 'Share Price Deviation'):
                        soup=BeautifulSoup(x['newslink'], 'lxml')
                        mylink = soup.find('a')
                        trim=mylink.attrs['href']
                        trim=trim.split('/url?q=')[1]
                        mylink.attrs['href']=trim
                        client_network['href']= str(mylink)
                    else:
                        soup=BeautifulSoup(x['newslink'], 'lxml')
                        mylink = soup.find('a')
                        trim=mylink.attrs['href']
                        trim='https://www.indiainfoline.com/top-news'+trim
                        mylink.attrs['href']=trim
                        client_network['href']= str(mylink)
                client_network['news_summary']=x['name']
                clients=list()
                for c in x['children']:
                    clients.append(c['name'])
                client_network['Client_Names']=clients
                client_network_list.append(client_network)

    return client_network_list

port = os.getenv('VCAP_APP_PORT', '8080')
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(port))
