import sys
import os
import getpass
import mimetypes
import zipfile
import re
import json
from datetime import datetime, date
from zipfile import ZIP_DEFLATED

try:
    import yaml
except:
    print("python pyyaml nicht installiert.\npip install pyyaml")
    exit()
    
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = 'https://epub-test.uni-regensburg.de'
VERIFY = False #Verify ssl certificate on request, has to be set false for the test server and should be true with valid ssl certificate

#packages that might have to be installed
try:
    import requests
except:
    print("python requests not installed.\npip install requests")
    exit()

try:
    import yaml
except:
    print("python yaml nicht installiert.\npip install PyYaml")
    exit()

from requests.auth import HTTPBasicAuth
import argparse

# Fix Python 2.x.
try:
   input = raw_input
except NameError:
   pass

"""
Sends a request to epub to upload one or multiple files

    Parameters
    ----------
    files : string
        File(s) to upload
    user : str
        eprints username
    epid : mixed
        default: false 
            creates new entry
        int: 
            attach files to eprint with given id
        
"""

def get_content_type(f):    
    #get the Content-type for a file- maybe magic should be used instead
    filename, file_extension = os.path.splitext(f)
    #mime_type.guess sometimes returns incorrect types in windows
    if file_extension == ".zip":
        return "application/zip"
    
    mime_type = mimetypes.guess_type(f)[0]
    if mime_type == None:
        mime_type = 'text/plain'
    
    return mime_type

def pretty_print_POST(req):
    """
    At this point it is completely built and ready
    to be fired; it is "prepared".

    However pay attention at the formatting used in 
    this function because it is programmed to be pretty 
    printed and may differ from the actual request.
    """
    print('{}\n{}\n{}\n\n{}'.format(
        '-----------START-----------',
        req.method + ' ' + req.url,
        '\n'.join('{}: {}'.format(k, v) for k, v in req.headers.items()),
        req.body,
    ))
def send_sword_request( data, content_type, send_file=False, headers={}, url=BASE_URL + '/id/contents', action='POST'):
    """Send a single SWORD request"""
    s = requests.Session()
            
    h = {'Content-Type': content_type, 'Accept-Charset': 'UTF-8'}
    headers.update(h)
    
    if send_file:
        f=data
        path, filename = os.path.split(f)
        
        zip = open(f, 'rb')
        files = {'file': (filename, zip, content_type)}             
        fc = {'Content-Disposition': 'attachment; filename=' + filename}
        headers.update(fc)
        r = requests.Request(action, url, files=files, headers=headers, auth=(user, password))  
    else:    
        r = requests.Request(action, url, data=data, headers=headers, auth=(user, password) )  
    
    if verbose:
        print(headers)
    prepared = r.prepare()
    if verbose:
        pretty_print_POST(prepared)
    
    #verify ssl certificate
    resp = s.send(prepared, verify=VERIFY)
    if verbose:
        print(resp.status_code)
        print(resp.raise_for_status())
        print(resp.headers)
    
    zip.close()
    
    if resp.status_code == 200 or resp.status_code == 201:
        if 'Location' in resp.headers:
            return resp.headers['Location']
        else:
            return 0;
    else:
        return -1

    
def get_document_ids(epid, yaml_timestamp=False, type='fileid'):
    """
    Gets ids for the pdf and xml zip in eprints

    Parameters
    ----------
    epid : int
        Eprint entry for the current measurements
    yaml_timestamp : date
        changedate of the yamlfile
	type : string
		If type is fileid return the ids of the file regardless of

    Returns
    -------
    docid : mixed
        False on error 
        -1 if zips are up to date
        int[] with xml.zip and pdf.zip at [0] and [1] respectively
    """
    s = requests.Session()
            
    headers = {'Accept': 'application/atom+xml', 'Accept-Charset': 'UTF-8'}   
    
    url = BASE_URL + "/id/eprint/" + str(epid) + "/contents"
    
    r = requests.Request('GET', url, headers=headers, auth=(user, password) )  
    
    if verbose:
        print(headers)
    prepared = r.prepare()
    #if verbose:
        #print(prepared)
        #print(prepared.body)
    
    #verify ssl certificate
    resp = s.send(prepared, verify=VERIFY)
    if verbose:
        print(resp.status_code)
        print(resp.raise_for_status())
        print(resp.headers)
        print(resp.text)
    
    if resp.status_code == 200 or resp.status_code == 201:
    
        regex = "application\/zip.*\/document\/\d+"
        #m = re.search(regex, resp.text)
        response = resp.text
        
        docid = []
        for match in re.findall(regex, response):
            m = re.search('(?<=\/document\/)\d+', match)
            
            if type!='fileid':
                docid.append(m.group(0))
                continue
            
            #read fileids; Eprints stores the files with ids, independent from the eprint id
            url = BASE_URL + "/id/document/" + str(m.group(0)) + "/contents"
            
            r = requests.Request('GET', url, headers=headers, auth=(user, password) ) 
            prepared = r.prepare()
            if verbose:
                print(resp.status_code)
                print(resp.raise_for_status())
                print(resp.headers)
                print(resp.text)
            resp = s.send(prepared, verify=VERIFY)
            if resp.status_code == 200 or resp.status_code == 201:
                ep_timestamp = re.search('(?<=\<updated\>).*(?=T)', resp.text)
                ep_timestamp = datetime.strptime(ep_timestamp.group(0), "%Y-%m-%d").date()
                if verbose:
                    if yaml_timestamp:
                        print("Yamlfile zuletzt geaendert: " + date.strftime(yaml_timestamp, "%Y-%m-%d"))
                    print("Eprints Datei zuletzt geaendert: " + date.strftime(ep_timestamp, "%Y-%m-%d"))
                
                #Compare timestamps of file with Eprints
                #if equal or yaml is newer, no update is needed
                if yaml_timestamp and yaml_timestamp <= ep_timestamp:
                    return -1
                
                m = re.search('(?<=file\/)\d+', resp.text)
                docid.append(m.group(0))
            
        return docid
            
    else:
        return False
    

def create_zips(path):
    #read xml and pdf files and zip both
    xmlzip = zipfile.ZipFile(path + 'xml.zip', 'w', ZIP_DEFLATED)
    pdfzip = zipfile.ZipFile(path + 'pdf.zip', 'w', ZIP_DEFLATED)
    
    for root, dirs, files in os.walk(path):
        for file in files:
            filename, extension = os.path.splitext(file)
            basename = filename + extension
            
            if extension in '.xml':
                xmlzip.write(os.path.join(root, file), file)
            elif extension in '.pdf':
                pdfzip.write(os.path.join(root, file), file)
            elif extension in '.yml':
                #TODO: throw error when more than one yaml file present
                yamlfile=os.path.join(root,file)
                xmlzip.write(os.path.join(root, file), file)
                pdfzip.write(os.path.join(root, file), file)


    xmlzip.close()
    pdfzip.close()
    
    return [yamlfile, xmlzip.filename, pdfzip.filename]

def create_ep_xml(xmlcontent):
    #Create atom xml file to create a new eprint
    filename = 'ep_metadata.xml'
    stream = open(filename, 'w')
    
    stream.write(xmlcontent)
    stream.close()
    
    return filename

#remove files after upload
def cleanup():
    try:
        #TODO: werden Dateien entfernt wenn eine davon nicht gefunden wird?
        os.remove(ep_xml_file)
        os.remove(pdfzip)
        os.remove(xmlzip)
        #pass
    except FileNotFoundError:
        pass
    
    
## MAIN ##
parser = argparse.ArgumentParser(description='Eprits SWORD client')
parser.add_argument('--path', '-p', type=str, help='Verzeichnis zum Hochladen')
parser.add_argument('--epid', '-i', type=int, help='Eprints Id zum anhengen oder false um neuen Eintrag zu erstellen')
parser.add_argument('--user', '-u', type=str, help='Eprints username')
parser.add_argument('--verbose', '-v', action='store_true', help='Zusaetzliche Informationen anzeigen')

args = parser.parse_args()

path = args.path
epid = args.epid
user = args.user
verbose = args.verbose

#If no path set, read from cmd
if path == None:
    path = input("Datei/Verzeichnis: ")

#file/folder exist?
assert os.path.exists(path), "Pfad nicht gefunden: " + str(path)
assert os.path.isdir(path), "Kein korrekter Verzeichnispfad " + str(path)

#os.chdir(path)

if user == None:
    user = input('Username: ')

if epid == None:
    epid = False

#User password
#TODO: we need some way to save this
password = getpass.getpass('Password:')

[yamlfile, xmlzip, pdfzip] = create_zips(path)

if verbose:
	print(yamlfile)

changeddate = date.fromtimestamp(os.path.getmtime(yamlfile))

stream = open(yamlfile, "r")
doc = yaml.load(stream)
title = doc['title']
author_list = doc['author']
author={}

#read/write finished flag
if 'finished' in doc.keys():
    print("Messung abgeschlossen!")
    cleanup()
    exit()

if 'epid' in doc.keys():
    epid = doc['epid']
    
for line in author_list:
   author.update(line)

#print(yaml.dump(doc))
stream.close()

#create a new Eprints id

#send metadata as xml request
first_name = author['firstName']
last_name = author['lastName']

ep_xml = """<?xml version='1.0' encoding='utf-8'?>
<eprints xmlns='http://eprints.org/ep2/data/2.0'>
    <eprint>
        <title>%s</title>
        <creators>
            <item>
            <name>
                <given>%s</given>
                <family>%s</family>
            </name>
            </item>
        </creators>
    </eprint>
</eprints>
""" % (title, first_name, last_name)


#TODO: get more infos from Eprints (Author, rz-kennung, orcid)
ep_xml_file = create_ep_xml(ep_xml)

headers={}

headers.update({'Content-Type': 'application/vnd.eprints.data+xml'})
#headers.update({'X-Requested-With': 'Python requests'})
#headers.update({'Content-Disposition': 'attachment; filename=' + ep_xml_file})

#es gibt schon einen Eintrag auf epub

if not epid:
    #create new entry
    data = open(ep_xml_file, 'rb').read()
    epid = send_sword_request(data, content_type='application/vnd.eprints.data+xml', send_file=False, headers=headers)

    if verbose:
        print("EPID: " + str(epid))

    m = re.search('[0-9]+$', str(epid))
    epid = m.group(0)

    print("Eprint mit id " + epid + " angelegt")
else:
    #Eprint entry already exists
    print("Eprint mit id " + str(epid) + " wird aktualisiert")
        
    
#update yamlfile stream = open(yamlfile, "r")
stream = open(yamlfile, "r")
doc = yaml.load(stream)
stream.close

#if new eprint was generated, update the yamlfile with its id
if not ('epid' in doc.keys()):
    #doc.update({'epid': epid})
    yaml_file = open(yamlfile, 'a') #append to file
    yaml_file.write("\n" + "epid: "+ epid)
    yaml_file.close()
    #read as yamlfile and write as plain text because pyyaml messes up the structure 

#with open(yamlfile, 'w') as outfile:
#    yaml.dump(doc, outfile, default_flow_style=False)

#yaml.dump(doc, yamlfile)

#print(yaml.dump(doc))
#outfile.close()

url=''
"""
if not epid:
    #erstelle neues eprints
    if verbose:
        print('Unerwarteter Eprints Fehler: Bitte rufen Sie das letzte Kommando mit -v auf um mehr Infos zu erhalten')
    exit()
    url = BASE_URL + "/id/contents"
else:
    #lade zu vorhandenem hoch
    url = BASE_URL + "/id/eprint/" + str(epid) + "/contents"
"""

docids = get_document_ids(epid, changeddate)


if docids:
    if docids == -1:
        print("Dateien bereits aktuell")
        cleanup()
        #print("Nothing to do here. *fliesaway*")
        exit()
    else:
        #check if files present and delete/update them
        for document in docids:
            print(document)


#url = BASE_URL + "/id/document/" + str(docids[0]) + "/contents"

#upload zipfiles
headers={}
up_file = pdfzip
send_sword_request(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/eprint/" + str(epid) + "/contents", action='POST')
#curl_send_file(pdfzip, url=BASE_URL + "/id/eprint/" + str(epid) + "/contents")
#docid = send_sword_request_pycurl(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/eprint/" + str(epid) + "/contents", action='POST')
headers={}
up_file = xmlzip
send_sword_request(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/eprint/" + str(epid) + "/contents", action='POST')


#headers={}
#up_file = pdfzip
if docids and len(docids) >= 1:
    send_sword_request(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/file/" + str(docids[0]), action='PUT')
else:
    send_sword_request(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/eprint/" + str(epid) + "/contents", action='POST')


#headers={}
#up_file = xmlzip
if docids and len(docids) >= 2:
    
    send_sword_request(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/file/" + str(docids[1]), action='PUT')
else:
    send_sword_request(up_file, content_type=get_content_type(up_file), send_file=True, headers=headers, url=BASE_URL + "/id/eprint/" + str(epid) + "/contents", action='POST')



#delete files after upload
cleanup()

#if os.path.isdir(path):
#    for f in os.listdir(path):
#else:
#    send_sword_request(path)