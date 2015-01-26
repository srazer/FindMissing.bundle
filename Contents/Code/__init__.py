####################################################################################################
#	This plugin will search the database and look for any missing files
#
#	Made by srazer
#	Based on code from Plex-findUnmatched by dane22 and myself
#
#
####################################################################################################

import os
import unicodedata
import string
import urllib
import io
import time

VERSION = ' V0.1.1'
NAME = 'FindMissing'
ART = 'art-default.jpg'
ICON = 'icon-FindMissing.png'
PREFIX = '/applications/findMissing'
MYHEADER = {}
APPGUID = '7608cf36-742b-11e4-8b39-00089b13a1c5'
DESCRIPTION = 'Show missing files'

myPathList = {}			# Contains dict of section keys and file-path
myResults = []			# Contains the end results
bScanStatus = 0			# Current status of the background scan
initialTimeOut = 10		# When starting a scan, how long in seconds to wait before displaying a status page. Needs to be at least 1.


####################################################################################################
# Start function
####################################################################################################
def Start():
#	print("********  Started %s on %s  **********" %(NAME  + VERSION, Platform.OS))
	Log.Debug("*******  Started %s on %s  ***********" %(NAME  + VERSION, Platform.OS))
	global MYHEADER
	Plugin.AddViewGroup('List', viewMode='List', mediaType='items')
	ObjectContainer.art = R(ART)
	ObjectContainer.title1 = NAME  + VERSION
	ObjectContainer.view_group = 'List'
	DirectoryObject.thumb = R(ICON)
	HTTP.CacheTime = 0
	getToken()
	ValidatePrefs()

#********** Get token from plex.tv *********
''' This will return a valid token, that can be used for authenticating if needed, to be inserted into the header '''
# DO NOT APPEND THE TOKEN TO THE URL...IT MIGHT BE LOGGED....INSERT INTO THE HEADER INSTEAD
@route(PREFIX + '/getToken')
def getToken():
	Log.Debug('Starting to get the token')
	if Prefs['Authenticate']:
		# Start by checking, if we already got a token
		if 'authentication_token' in Dict and Dict['authentication_token'] != 'NuKeMe' and Dict['authentication_token'] != '':
			Log.Debug('Got a token from local storage')
			global MYHEADER
			MYHEADER['X-Plex-Token'] = Dict['authentication_token']
		else:
			Log.Debug('Need to generate a token first from plex.tv')
			userName = Prefs['Plex_User']
			userPwd = Prefs['Plex_Pwd']
			myUrl = 'https://plex.tv/users/sign_in.json'
			# Create the authentication string
			base64string = String.Base64Encode('%s:%s' % (userName, userPwd))
			# Create the header
			MYAUTHHEADER= {}
			MYAUTHHEADER['X-Plex-Product'] = DESCRIPTION
			MYAUTHHEADER['X-Plex-Client-Identifier'] = APPGUID
			MYAUTHHEADER['X-Plex-Version'] = VERSION
			MYAUTHHEADER['Authorization'] = 'Basic ' + base64string
			MYAUTHHEADER['X-Plex-Device-Name'] = NAME
			# Send the request
			try:
				httpResponse = HTTP.Request(myUrl, headers=MYAUTHHEADER, method='POST')
				myToken = JSON.ObjectFromString(httpResponse.content)['user']['authentication_token']
				Log.Debug('Response from plex.tv was : %s' %(httpResponse.headers["status"]))
			except:
				Log.Critical('Exception happend when trying to get a token from plex.tv')
				Log.Critical('Returned answer was %s' %httpResponse.content)
				Log.Critical('Status was: %s' %httpResponse.headers) 			
			Dict['authentication_token'] = myToken
			Dict.Save()
			global MYHEADER
			MYHEADER['X-Plex-Token'] = Dict['authentication_token']
	else:
			Log.Debug('Authentication disabled')
	ValidatePrefs()

####################################################################################################
# Main menu
####################################################################################################
@handler(PREFIX, NAME, thumb=ICON, art=ART)
@route(PREFIX + '/MainMenu')
def MainMenu(random=0):
	Log.Debug("**********  Starting MainMenu  **********")
	oc = ObjectContainer()
	
	# Clear the myPathList
	myPathList.clear
	try:
		sections = XML.ElementFromURL(Dict['PMS_URL'], headers=MYHEADER).xpath('//Directory')
		for section in sections:
			sectiontype = section.get('type')
			title = section.get('title')
			key = section.get('key')
			paths = section.xpath('Location/@path')
			Log.Debug("Title of section is %s with a key of %s and a path of : %s" %(title, key, paths))
			myPathList[key]= ', '.join(paths)
			oc.add(DirectoryObject(key=Callback(backgroundScan, title=title, sectiontype=sectiontype, key=key, random=time.clock()), title='Look in section "' + title + '"', summary='Look for missing files in "' + title + '"'))
	except:
		Log.Critical("Exception happened in MainMenu")
		raise
	oc.add(PrefsObject(title='Preferences', thumb=R('icon-prefs.png')))
	Log.Debug("**********  Ending MainMenu  **********")
	return oc

####################################################################################################
# Called by the framework every time a user changes the prefs
####################################################################################################
@route(PREFIX + '/ValidatePrefs')
def ValidatePrefs():
	if Prefs['NukeToken']:
		# My master wants to nuke the local store
		Log.Debug('Removing Token from local storage')
		Dict['authentication_token'] = 'NuKeMe'
		Dict.Save()
		Log.Debug('Resetting flag to nuke token')
		# My master has nuked the local store, so reset the prefs flag
		myHTTPPrefix = 'http://127.0.0.1:32400/:/plugins/com.plexapp.plugins.findUnmatch/prefs/'
		myURL = myHTTPPrefix + 'set?NukeToken=0'
		Log.Debug('Prefs Sending : ' + myURL)
		HTTP.Request(myURL, immediate=True, headers=MYHEADER)
		# Get new token
		getToken()
	# If the host pref is missing the port, add it.
	if Prefs['host'].find(':') == -1:
		host = Prefs['host'] + ':32400'
		HTTP.Request('http://' + host + '/:/plugins/com.plexapp.plugins.findUnmatch/prefs/set?host=' + host, immediate=True, headers=MYHEADER)
	Dict['PMS_URL'] = 'http://%s/library/sections/' %(Prefs['host'])
	# Verify Server
	try:
		HTTP.Request('http://' + Prefs['host'], immediate=True)
		Log.Debug("Host: %s verified successfully" %(Prefs['host']))
	except:
		Log.Debug("Unable to reach server: %s resetting to 127.0.0.1:32400" %('http://' + Prefs['host']))
		HTTP.Request('http://127.0.0.1:32400/:/plugins/com.plexapp.plugins.findUnmatch/prefs/set?host=127.0.0.1:32400', immediate=True, headers=MYHEADER)

####################################################################################################
# Display The Results
####################################################################################################
@route(PREFIX + '/results')
def results(title):
	Log.Debug("*******  Starting compare  ***********")
	global bScanStatus
	global myResults
	Log.Info("*********************** The END RESULT Start *****************")
	Log.Info("****** Found %d Items missing **************" %(len(myResults)))
	Log.Info("The following files are missing in Plex database from section named: %s:" %(title))
	if len(myResults) == 0:
		myResults.append("All is good....no files are missing")
	Log.Info(myResults)
	Log.Info("*********************** The END RESULT End *****************")
	Log.Debug("*******  Ending confirmScan  ***********")
	foundNo = len(myResults)
	if foundNo == 1:
		if "All is good....no files are missing" in myResults:
			foundNo = 0
	title = ("%d missing items found." %(foundNo))
	oc2 = ObjectContainer(title1=title, no_cache=True)
	counter = 1
	for item in myResults:
		title=item.decode('utf-8','ignore')
                title2=title
                if title[0] == '[':
			title = title[1:]
		if title[len(title)-1] == ']':
			title = title[:-1]
		title = str(counter) + ": " + title
		counter += 1
		oc2.add(DirectoryObject(key=Callback(MainMenu, random=time.clock()), title=title, summary="Missing file: \n\n"+title2))

	# Reset the scanner status
	bScanStatus = 0
	return oc2
####################################################################################################
# This function will scan a movie section for missing files.
####################################################################################################
@route(PREFIX + '/scanMovieDB')
def scanMovieDB(myMediaURL):
	Log.Debug("******* Starting scanMovieDB with an URL of %s***********" %(myMediaURL))
	global myResults
	global bScanStatusCount
	global bScanStatusCountOf
	bScanStatusCount = 0
	bScanStatusCountOf = 0
	myResults[:] = []
	myTmpPath = []
	try:
		myMedias = XML.ElementFromURL(myMediaURL, headers=MYHEADER).xpath('//Video')
		bScanStatusCountOf = len(myMedias)
		for myMedia in myMedias:
			title = myMedia.get('title')			
			myTmpPaths = (',,,'.join(myMedia.xpath('Media/Part/@file')).split(',,,'))
			for myTmpPath in myTmpPaths:
				filename = urllib.unquote(myTmpPath).decode('utf8')
				composed_filename = unicodedata.normalize('NFKC', filename)
				bScanStatusCount += 1
				if os.path.exists(filename.encode('utf8')):
					Log.Debug("Media #%s from database: '%s' exists with a path of: %s" %(bScanStatusCount, title, composed_filename))
				else:
					Log.Debug("Media #%s from database: '%s' is missing with a path of: %s" %(bScanStatusCount, title, composed_filename))
					myResults.append(composed_filename)
	except:
		Log.Critical("Detected an exception in scanMovieDB")
		bScanStatus = 99
		raise
	Log.Debug("******* Ending scanMovieDB ***********")

####################################################################################################
# This function will scan a photo section for missing files.
####################################################################################################
@route(PREFIX + '/scanPhotoDB')
def scanPhotoDB(myMediaURL):
	Log.Debug("******* Starting scanPhotoDB with an URL of %s***********" %(myMediaURL))
	global myResults
	global bScanStatusCount
	global bScanStatusCountOf
	bScanStatusCount = 0
	bScanStatusCountOf = 0
	bScanStatusFileCount = 0
	myResults[:] = []
	myTmpPath = []
	dirKeys = []
	try:
	
	# Get all keys
		Log.Debug("Getting all folder keys.")
		# Get all root keys
		myMedias = XML.ElementFromURL(myMediaURL, headers=MYHEADER).xpath('//Directory')
		for myMedia in myMedias:
			ratingKey = myMedia.get("ratingKey")
			dirKeys.append(ratingKey)

		# Scan all dirs for more dir keys
		for key in dirKeys:
			myURL = "http://" + Prefs['host'] + "/library/metadata/" + key + "/children"
			myMedias2 = XML.ElementFromURL(myURL, headers=MYHEADER).xpath('//Directory')
			for myMedia2 in myMedias2:
				ratingKey = myMedia2.get("ratingKey")
				Log.Debug("Adding key %s" %(ratingKey))
				dirKeys.append(ratingKey)

		Log.Debug("%s keys found: %s" %(len(dirKeys), dirKeys))
		bScanStatusCountOf = len(dirKeys) + 1 # +1 to include the root dir

	# Scan for photos
		Log.Debug("Scanning files.")
		# Scan photos in root folder
		bScanStatusCount += 1
		myMedias = XML.ElementFromURL(myMediaURL, headers=MYHEADER).xpath('//Photo')
		for myMedia in myMedias:
			myTmpPaths = (',,,'.join(myMedia.xpath('Media/Part/@file')).split(',,,'))
			for myTmpPath in myTmpPaths:
				bScanStatusFileCount += 1
				filename = urllib.unquote(myTmpPath).decode('utf8')
				composed_filename = unicodedata.normalize('NFKC', filename)
				if os.path.exists(filename.encode('utf8')):
					Log.Debug("Media #%s exists with a path of: %s" %(bScanStatusFileCount, composed_filename))
				else:
					Log.Debug("Media #%s is missing with a path of: %s" %(bScanStatusFileCount, composed_filename))
					myResults.append(composed_filename)

		# Scan photos in sub folders
		for key in dirKeys:
			bScanStatusCount += 1
			myURL = "http://" + Prefs['host'] + "/library/metadata/" + key + "/children"
			myMedias = XML.ElementFromURL(myURL, headers=MYHEADER).xpath('//Photo')
			for myMedia in myMedias:
				myTmpPaths = (',,,'.join(myMedia.xpath('Media/Part/@file')).split(',,,'))
				for myTmpPath in myTmpPaths:
					bScanStatusFileCount += 1
					filename = urllib.unquote(myTmpPath).decode('utf8')
					composed_filename = unicodedata.normalize('NFKC', filename)
					if os.path.exists(filename.encode('utf8')):
						Log.Debug("Media #%s exists with a path of: %s" %(bScanStatusFileCount, composed_filename))
					else:
						Log.Debug("Media #%s is missing with a path of: %s" %(bScanStatusFileCount, composed_filename))
						myResults.append(composed_filename)

	except:
		Log.Critical("Detected an exception in scanPhotoDB")
		bScanStatus = 99
		raise
	Log.Debug("******* Ending scanPhotoDB ***********")

####################################################################################################
# This function will scan a TV-Show section for missing files.
####################################################################################################
@route(PREFIX + '/scanShowDB')
def scanShowDB(myMediaURL):
	Log.Debug("******* Starting scanShowDB with an URL of %s***********" %(myMediaURL))
	global bScanStatusCount
	global bScanStatusCountOf
	global myResults
	global myMedias
	myResults[:] = []
	bScanStatusCount = 0

	try:
		myMedias = XML.ElementFromURL(myMediaURL, headers=MYHEADER).xpath('//Directory')
		bScanStatusCountOf = len(myMedias)
		for myMedia in myMedias:
			bScanStatusCount += 1
			ratingKey = myMedia.get("ratingKey")
			myURL = "http://" + Prefs['host'] + "/library/metadata/" + ratingKey + "/allLeaves"
			Log.Debug("Show %s of %s with a RatingKey of %s at myURL: %s" %(bScanStatusCount, bScanStatusCountOf, ratingKey, myURL))
			myMedias2 = XML.ElementFromURL(myURL, headers=MYHEADER).xpath('//Video')
			for myMedia2 in myMedias2:
				title = myMedia2.get("grandparentTitle") + "/" + myMedia2.get("title")
				# Using three commas as one has issues with some filenames.
				myFilePath = (',,,'.join(myMedia2.xpath('Media/Part/@file')).split(',,,'))
				for myFilePath2 in myFilePath:
					filename = urllib.unquote(myFilePath2).decode('utf8')
					composed_filename = unicodedata.normalize('NFKC', filename)
					if os.path.exists(filename.encode('utf8')):
						Log.Debug("Media from database: '%s' exists with a path of: %s" %(title, composed_filename))
					else:
						Log.Debug("Media from database: '%s' is missing with a path of: %s" %(title, composed_filename))
						myResults.append(composed_filename)
	except:
		Log.Critical("Detected an exception in scanShowDB")
		bScanStatus = 99
		raise # Dumps the error so you can see what the problem is
	Log.Debug("******* Ending scanShowDB ***********")

####################################################################################################
# This function will scan a Music section for missing files.
####################################################################################################
@route(PREFIX + '/scanArtistDB')
def scanArtistDB(myMediaURL):
	Log.Debug("******* Starting scanArtistDB with an URL of %s***********" %(myMediaURL))
	global bScanStatusCount
	global bScanStatusCountOf
	global myResults
	myResults[:] = []
	try:
		myMedias = XML.ElementFromURL(myMediaURL, headers=MYHEADER).xpath('//Directory')
		bScanStatusCountOf = len(myMedias)
		for myMedia in myMedias:
			bScanStatusCount += 1
			ratingKey = myMedia.get("ratingKey")
			myURL = "http://" + Prefs['host'] + "/library/metadata/" + ratingKey + "/allLeaves"
			Log.Debug("%s of %s with a RatingKey of %s at myURL: %s" %(bScanStatusCount, bScanStatusCountOf, ratingKey, myURL))
			myMedias2 = XML.ElementFromURL(myURL, headers=MYHEADER).xpath('//Track')
			for myMedia2 in myMedias2:
				title = myMedia2.get("grandparentTitle") + "/" + myMedia2.get("title")
				# This returns a double backslash for every backslash
				#myFilePath = str(myMedia2.xpath('Media/Part/@file'))[2:-2]
				# This appears to work fine
				myFilePath = ',,,'.join(myMedia2.xpath('Media/Part/@file'))
				filename = urllib.unquote(myFilePath).decode('utf8')
				composed_filename = unicodedata.normalize('NFKC', filename)
				if os.path.exists(filename.encode('utf8')):
					Log.Debug("Media from database: '%s' exists with a path of: %s" %(title, composed_filename))
				else:
					Log.Debug("Media from database: '%s' is missing with a path of: %s" %(title, composed_filename))
					myResults.append(composed_filename)
	except:
		Log.Critical("Detected an exception in scanArtistDB")
		bScanStatus = 99
		raise
	Log.Debug("******* Ending scanArtistDB ***********")

####################################################################################################
# Start the scanner in a background thread and provide status while running
####################################################################################################
@route(PREFIX + '/backgroundScan')
def backgroundScan(title, key, sectiontype, random=0):
	Log.Debug("******* Starting backgroundScan *********")
	# Current status of the Background Scanner:
	# 0=not running, 1=running, 2=complete, 
	# Errors: 99=Other Error
	global bScanStatus
	# Current status count (ex. "Show 2 of 31")
	global bScanStatusCount
	global bScanStatusCountOf
	try:
		if bScanStatus == 0:
			bScanStatusCount = 0
			bScanStatusCountOf = 0
			# Start scanner
			Thread.Create(backgroundScanThread, globalize=True, title=title, key=key, sectiontype=sectiontype)
			# Wait 10 seconds unless the scanner finishes
			x = 0
			while (x <= initialTimeOut):
				time.sleep(1)
				x += 1
				if bScanStatus == 2:
					Log.Debug("************** Scan Done, stopping wait **************")
					oc2 = results(title=title)
					return oc2
					break
				if bScanStatus >= 90:
					Log.Debug("************** Error in thread, stopping wait **************")
					break
		# Summary to add to the status
		summary = "The Plex client will only wait a few seconds for us to work, so we run it in the background. This requires you to keep checking on the status until it is complete. \n\n"
		if bScanStatus == 1:
			# Scanning
			summary = summary + "Looking for missing files. \nScanning " + str(bScanStatusCount) + " of " + str(bScanStatusCountOf) + ". \nPlease wait a few seconds and check the status again."
			oc2 = ObjectContainer(title1="Scanning " + str(bScanStatusCount) + " of " + str(bScanStatusCountOf) + ".", no_history=True)
			oc2.add(DirectoryObject(key=Callback(backgroundScan, random=time.clock(), title=title, sectiontype=sectiontype, key=key), title="Looking for missing files. Click to refresh status.", summary=summary))
			oc2.add(DirectoryObject(key=Callback(backgroundScan, random=time.clock(), title=title, sectiontype=sectiontype, key=key), title="Scanning " + str(bScanStatusCount) + " of " + str(bScanStatusCountOf), summary=summary))
			return oc2
		elif bScanStatus == 2:
			# See Results
			summary = "Scan complete, click here to get the results."
			oc2 = ObjectContainer(title1="Results", no_history=True)
			oc2.add(DirectoryObject(key=Callback(results, title=title), title="*** Get the Results. ***", summary=summary))
		elif bScanStatus == 99:
			# Error condition set by scanner
			summary = "An internal error has occurred. Please check the logs"
			oc2 = ObjectContainer(title1="Internal Error Detected. Please check the logs",no_history=True)
			oc2.add(DirectoryObject(key=Callback(backgroundScan, random=time.clock(), title=title, sectiontype=sectiontype, key=key), title="An internal error has occurred.", summary=summary))
			bScanStatus = 0
		else:
			# Unknown status. Should not happen.
			summary = "Something went horribly wrong. The scanner returned an unknown status."
			oc2 = ObjectContainer(title1="Uh Oh!.", no_history=True)
			oc2.add(DirectoryObject(key=Callback(backgroundScan, random=time.clock(), title=title, sectiontype=sectiontype, key=key), title="*** Unknown status from scanner ***", summary=summary))
	except:
		Log.Critical("Detected an exception in backgroundScan")
		raise
	Log.Debug("******* Ending backgroundScan ***********")
	return oc2


####################################################################################################
# Background scanner thread.
####################################################################################################
@route(PREFIX + '/backgroundScanThread')
def backgroundScanThread(title, key, sectiontype):
	Log.Debug("*******  Starting backgroundScanThread  ***********")
	global myResults
	global myPathList
	global bScanStatus
	global bScanStatusCount
	global bScanStatusCountOf
	
	try:
		bScanStatus = 1
		Log.Debug("Section type is %s" %(sectiontype))
		myMediaURL = Dict['PMS_URL'] + key + "/all"		
		Log.Debug("Path to medias in section is %s" %(myMediaURL))

		# Scan the database based on the type of section
		if sectiontype == "movie":
			scanMovieDB(myMediaURL)
		if sectiontype == "artist":
			scanArtistDB(myMediaURL)
		if sectiontype == "show":
			scanShowDB(myMediaURL)
		if sectiontype == "photo":
			scanPhotoDB(myMediaURL)
		
		# Stop scanner on error
		if bScanStatus >= 90: return

		global myResults
		bScanStatus = 2

	except:
		Log.Critical("Exception happened in backgroundScanThread")
		bScanStatus = 99
		raise
	Log.Debug("*******  Ending backgroundScanThread  ***********")

