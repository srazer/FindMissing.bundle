####################################################################################################
#	This plugin will search the database and look for any missing files
#
#	Made by s_razer
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

VERSION = ' V0.0.1'
NAME = 'FindMissing'
ART = 'art-default.jpg'
ICON = 'icon-FindUnmatched.png'
PREFIX = '/applications/findMissing'

myPathList = {}			# Contains dict of section keys and file-path
myResults = []			# Contains the end results
bScanStatus = 0			# Current status of the background scan
initialTimeOut = 10		# When starting a scan, how long in seconds to wait before displaying a status page. Needs to be at least 1.


####################################################################################################
# Start function
####################################################################################################
def Start():
	print("********  Started %s on %s  **********" %(NAME  + VERSION, Platform.OS))
	Log.Debug("*******  Started %s on %s  ***********" %(NAME  + VERSION, Platform.OS))
	Plugin.AddViewGroup('List', viewMode='List', mediaType='items')
	ObjectContainer.art = R(ART)
	ObjectContainer.title1 = NAME  + VERSION
	ObjectContainer.view_group = 'List'
	DirectoryObject.thumb = R(ICON)
	HTTP.CacheTime = 0
	getPrefs()

####################################################################################################
# Main menu
####################################################################################################
@handler(PREFIX, NAME, thumb=ICON, art=ART)
@route(PREFIX + '/MainMenu')
def MainMenu(random=0):
	Log.Debug("**********  Starting MainMenu  **********")
	getPrefs()
	oc = ObjectContainer()
	
	# Clear the myPathList
	myPathList.clear
	try:
		sections = XML.ElementFromURL(PMS_URL).xpath('//Directory')
		for section in sections:
			sectiontype = section.get('type')
			if sectiontype != "photo":
				title = section.get('title')
				key = section.get('key')
				paths = section.xpath('Location/@path')
				Log.Debug("Title of section is %s with a key of %s and a path of : %s" %(title, key, paths))
				myPathList[key]= ', '.join(paths)
				oc.add(DirectoryObject(key=Callback(backgroundScan, title=title, sectiontype=sectiontype, key=key, random=time.clock()), title='Look in section "' + title + '"', summary='Look for unmatched files in "' + title + '"'))
	except:
		Log.Critical("Exception happened in MainMenu")
		raise
	oc.add(PrefsObject(title='Preferences', thumb=R('icon-prefs.png')))
	Log.Debug("**********  Ending MainMenu  **********")
	return oc

####################################################################################################
# Get user settings, and if not existing, get the defaults
####################################################################################################
@route(PREFIX + '/getPrefs')
def getPrefs():
	Log.Debug("*********  Starting to get User Prefs  ***************")
	global host
	host = Prefs['host']
	if host.find(':') == -1:
		host += ':32400'
	global PMS_URL
	PMS_URL = 'http://%s/library/sections/' %(host)
	Log.Debug("PMS_URL is : %s" %(PMS_URL))
	Log.Debug("*********  Ending get User Prefs  ***************")
	return

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
		oc2.add(DirectoryObject(key=Callback(MainMenu, random=time.clock()), title=title, summary="Unmatched file: \n\n"+title2))

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
		myMedias = XML.ElementFromURL(myMediaURL).xpath('//Video')
		bScanStatusCountOf = len(myMedias)
		for myMedia in myMedias:
			title = myMedia.get('title')			
			myTmpPaths = (',,,'.join(myMedia.xpath('Media/Part/@file')).split(',,,'))
			for myTmpPath in myTmpPaths:
				filename = urllib.unquote(myTmpPath).decode('utf8')
				composed_filename = unicodedata.normalize('NFKC', filename)
				myFilePath = urllib.quote(composed_filename.encode('utf8'))
				# Remove esc backslash if present and on Windows
				if Platform.OS == "Windows":
					myFilePath = myFilePath.replace(':%5C%5C', ':%5C')
				bScanStatusCount += 1
				if os.path.exists(filename):
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
		myMedias = XML.ElementFromURL(myMediaURL).xpath('//Directory')
		bScanStatusCountOf = len(myMedias)
		for myMedia in myMedias:
			bScanStatusCount += 1
			ratingKey = myMedia.get("ratingKey")
			myURL = "http://" + host + "/library/metadata/" + ratingKey + "/allLeaves"
			Log.Debug("Show %s of %s with a RatingKey of %s at myURL: %s" %(bScanStatusCount, bScanStatusCountOf, ratingKey, myURL))
			myMedias2 = XML.ElementFromURL(myURL).xpath('//Video')
			for myMedia2 in myMedias2:
				title = myMedia2.get("grandparentTitle") + "/" + myMedia2.get("title")
				# Using three commas as one has issues with some filenames.
				myFilePath = (',,,'.join(myMedia2.xpath('Media/Part/@file')).split(',,,'))
				for myFilePath2 in myFilePath:
					filename = urllib.unquote(myFilePath2).decode('utf8')
					composed_filename = unicodedata.normalize('NFKC', filename)
					myFilePath2 = urllib.quote(composed_filename.encode('utf8'))
					# Remove esc backslash if present and on Windows
					# The Colon prevents breaking Windows file shares.
					if Platform.OS == "Windows":
						myFilePath2 = myFilePath2.replace(':%5C%5C', ':%5C')
					if os.path.exists(filename):
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
		myMedias = XML.ElementFromURL(myMediaURL).xpath('//Directory')
		bScanStatusCountOf = len(myMedias)
		for myMedia in myMedias:
			bScanStatusCount += 1
			ratingKey = myMedia.get("ratingKey")
			myURL = "http://" + host + "/library/metadata/" + ratingKey + "/allLeaves"
			Log.Debug("%s of %s with a RatingKey of %s at myURL: %s" %(bScanStatusCount, bScanStatusCountOf, ratingKey, myURL))
			myMedias2 = XML.ElementFromURL(myURL).xpath('//Track')
			for myMedia2 in myMedias2:
				title = myMedia2.get("grandparentTitle") + "/" + myMedia2.get("title")
				# This returns a double backslash for every backslash
				#myFilePath = str(myMedia2.xpath('Media/Part/@file'))[2:-2]
				# This appears to work fine
				myFilePath = ',,,'.join(myMedia2.xpath('Media/Part/@file'))
				filename = urllib.unquote(myFilePath).decode('utf8')
				composed_filename = unicodedata.normalize('NFKC', filename)
				myFilePath = urllib.quote(composed_filename.encode('utf8'))
				# Remove esc backslash if present and on Windows
				if Platform.OS == "Windows":
					myFilePath = myFilePath.replace(':%5C%5C', ':%5C')
				if os.path.exists(filename):
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
			oc2.add(DirectoryObject(key=Callback(backgroundScan, random=time.clock(), title=title, sectiontype=sectiontype, key=key), title="Looking for missing files. Check Status.", summary=summary))
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
		myMediaURL = PMS_URL + key + "/all"		
		Log.Debug("Path to medias in section is %s" %(myMediaURL))

		# Scan the database based on the type of section
		if sectiontype == "movie":
			scanMovieDB(myMediaURL)
		if sectiontype == "artist":
			scanArtistDB(myMediaURL)
		if sectiontype == "show":
			scanShowDB(myMediaURL)
		# Stop scanner on error
		if bScanStatus >= 90: return

		global myResults
		bScanStatus = 2

	except:
		Log.Critical("Exception happened in backgroundScanThread")
		bScanStatus = 99
		raise
	Log.Debug("*******  Ending backgroundScanThread  ***********")

