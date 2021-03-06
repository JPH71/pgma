﻿# WayBig (IAFD)
import datetime, linecache, platform, os, re, string, sys, urllib

# Version / Log Title 
VERSION_NO = '2019.08.12.0'
PLUGIN_LOG_TITLE = 'WayBig'

# Pattern: (Studio) - Title (Year).ext: ^\((?P<studio>.+)\) - (?P<title>.+) \((?P<year>\d{4})\)
# if title on website has a hyphen in its title that does not correspond to a colon replace it with an em dash in the corresponding position
FILEPATTERN = Prefs['regex']

# URLS
WAYBIG_BASEURL = 'https://www.waybig.com'
WAYBIG_SEARCH_MOVIES = WAYBIG_BASEURL + '/blog/index.php?s=%s'

def Start():
    HTTP.CacheTime = CACHE_1WEEK
    HTTP.Headers['User-agent'] = 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)'

def ValidatePrefs():
    pass

class WAYBIGAgent(Agent.Movies):
    name = 'WayBig (IAFD)'
    languages = [Locale.Language.NoLanguage, Locale.Language.English]
    fallback_agent = False
    primary_provider = False
    preference = True
    media_types = ['Movie']
    contributes_to = ['com.plexapp.agents.cockporn']
    accepts_from = ['com.plexapp.agents.localmedia']

    def matchedFilename(self, file):
        # match file name to regex
        pattern = re.compile(FILEPATTERN)
        return pattern.search(file)

    def getFilenameGroups(self, file):
        # return groups from filename regex match
        pattern = re.compile(FILEPATTERN)
        matched = pattern.search(file)
        if matched:
            groups = matched.groupdict()
            groupstitle = groups['title']
            if ' - Disk ' in groupstitle:
                groupstitle = groupstitle.split(' - Disk ')[0]
            if ' - Disc ' in groupstitle:
                groupstitle = groupstitle.split(' - Disc ')[0]
            return groups['studio'], groupstitle, groups['year']

    # Normalise string for Comparison, strip all non alphanumeric characters, Vol., Volume, Part, and 1 in series
    def NormaliseComparisonString(self, myString):
        # convert to lower case and trim
        myString = myString.strip().lower()

        # convert sort order version to normal version i.e "Best of Zak Spears, The -> the Best of Zak Spears"
        if myString.count(', the'):
            myString = 'the ' + myString.replace(', the', '', 1)
        if myString.count(', An'):
            myString = 'an ' + myString.replace(', an', '', 1)
        if myString.count(', a'):
            myString = 'a ' + myString.replace(', a', '', 1)

        # remove vol/volume/part and vol.1 etc wording as filenames dont have these to maintain a uniform search across all websites and remove all non alphanumeric characters
        myString = myString.replace('&', 'and').replace(' 1', '').replace(' vol.', '').replace(' volume', '').replace(' part ','')

        # strip diacritics
        myString = String.StripDiacritics(myString)

        # remove all non alphanumeric chars
        regex = re.compile(r'\W+')
        return regex.sub('', myString)

    # check IAFD web site for better quality siteActor thumbnails irrespective of whether we have a thumbnail or not
    def getIAFDsiteActorImage(self, siteActor):
        IAFD_siteActor_URL = 'http://www.iafd.com/person.rme/perfid=FULLNAME/gender=SEX/FULL_NAME.htm'
        photourl = None
        siteActor = siteActor.lower()
        fullname = siteActor.replace(' ','').replace("'", '').replace(".", '')
        full_name = siteActor.replace(' ','-').replace("'", '&apos;')

        # siteActors are categorised on iafd as male or director in order of likelihood
        for gender in ['m', 'd']:
            iafd_url = IAFD_siteActor_URL.replace("FULLNAME", fullname).replace("FULL_NAME", full_name).replace("SEX", gender)
            self.log('SELF:: siteActor  %s - IAFD url: %s', siteActor, iafd_url)
            # Check URL exists and get siteActors thumbnail
            try:
                html = HTML.ElementFromURL(iafd_url)
                photourl = html.xpath('//*[@id="headshot"]/img')[0].get('src')
                photourl = photourl.replace('headshots/', 'headshots/thumbs/th_')
                if 'nophoto340.jpg' in photourl:
                    photourl = None
                return photourl
            except: 
                self.log('SELF:: NO IAFD siteActor Page')

    def log(self, message, *args):
        if Prefs['debug']:
            Log(PLUGIN_LOG_TITLE + ' - ' + message, *args)

    def search(self, results, media, lang, manual):
        self.log('-----------------------------------------------------------------------')
        self.log('SEARCH:: Version - v.%s', VERSION_NO)
        self.log('SEARCH:: Platform - %s %s', platform.system(), platform.release())
        self.log('SEARCH:: Prefs->debug - %s', Prefs['debug'])
        self.log('SEARCH::      ->regex - %s', FILEPATTERN)
        self.log('SEARCH:: media.title - %s', media.title)
        self.log('SEARCH:: media.items[0].parts[0].file - %s', media.items[0].parts[0].file)
        self.log('SEARCH:: media.items - %s', media.items)
        self.log('SEARCH:: media.filename - %s', media.filename)
        self.log('SEARCH:: lang - %s', lang)
        self.log('SEARCH:: manual - %s', manual)
        self.log('-----------------------------------------------------------------------')

        folder, file = os.path.split(os.path.splitext(media.items[0].parts[0].file)[0])
        self.log('SEARCH:: File Name: %s', file)
        self.log('SEARCH:: Enclosing Folder: %s', folder)
 
        # Check filename format
        if not self.matchedFilename(file):
            self.log('SEARCH:: Skipping %s because the file name is not in the expected format: (Studio) - Title (Year)', file)
            return

        group_studio, group_title, group_year = self.getFilenameGroups(file)
        self.log('SEARCH:: Processing: Studio: %s   Title: %s   Year: %s', group_studio, group_title, group_year)

        #  Release date default to december 31st of Filename value compare against release date on website
        compareReleaseDate = datetime.datetime(int(group_year), 12, 31)

        # saveTitle corresponds to the real title of the movie.
        saveTitle = group_title
        self.log('SEARCH:: Original Group Title: %s', saveTitle)

        # WayBig displays its movies as Studio: Title 
        searchTitle = group_studio + ' ' + saveTitle.split("‘")[0]
        compareTitle = self.NormaliseComparisonString(searchTitle)

        searchTitle = String.StripDiacritics(searchTitle).lower()
        
        # Search Query - for use to search the internet
        searchQuery = WAYBIG_SEARCH_MOVIES % String.URLEncode(searchTitle)
        self.log('SEARCH:: Search Query: %s', searchQuery) 

        html = HTML.ElementFromURL(searchQuery, timeout=90, errors='ignore')
        titleList = html.xpath('.//div[contains(@class,"main-blog-content")]/div[contains(@class,"content")]')
        for title in titleList:
            # if set it will enable the process to change the filename on disk to correspond to the waybig entry
            # files still need to be named in correct format e.g (Timtales) - XXXX plays ith YYYY (1900)
            # this code finds the actors in the title and matches them to the entry on waybig
            if Prefs['rename']:
                siteTitle = title.xpath('.//h2[contains (@class,"entry-title") and (@id)]/a/text()')[0]
                self.log('Title = %s', siteTitle)
                if group_studio in siteTitle:
                    siteURL = title.xpath('.//h2[contains(@class,"entry-title") and (@id)]/a/@href')[0]
                    siteReleaseDate = datetime.datetime(int(siteURL.split('/')[4]), int(siteURL.split('/')[5]), int(siteURL.split('/')[6]))
                    siteCastList = title.xpath('.//div[contains(@class,"entry-meta")]/ul/li[2]/a[contains(@href,"https://www.waybig.com/blog/tag/")]/text()')
                    self.log('Actors Listed = %s', siteCastList)

                    if len(siteCastList) > 1:
                        allPresent = True
                        for siteActor in siteCastList:
                            if not siteActor.lower() in file.lower():
                                allPresent = False

                        if allPresent == True:
                            movie = siteTitle
                            if ':' in movie:
                                movie = movie.split(':')[1].strip()
                            nfolder, ext = os.path.split(os.path.splitext(media.items[0].parts[0].file)[1])
                            newname = '%s\(%s) - %s (%s)%s' % (folder, group_studio, movie, siteReleaseDate.year, ext)
                            self.log('New File Name = %s', newname)
                            if media.items[0].parts[0].file != newname:
                                os.rename(media.items[0].parts[0].file, newname)
                continue

            siteTitle = title.xpath('.//h2[contains (@class, "entry-title") and (@id)]/a/text()')[0]
            siteTitle = self.NormaliseComparisonString(siteTitle)
            self.log('SEARCH:: Title Match: [%s] Compare Title - Site Title "%s - %s"', (compareTitle == siteTitle), compareTitle, siteTitle)
            if siteTitle != compareTitle:
                if siteTitle.replace(group_studio.lower(),'') != compareTitle.replace(group_studio.lower(),''):
                    continue

            # curID = the ID portion of the href in 'movie'
            siteURL = title.xpath('.//h2[contains(@class,"entry-title") and (@id)]/a/@href')[0]
            self.log('SEARCH:: Site Title URL: %s' % str(siteURL))

            # Get thumbnail image - store it with the CURID for use during updating
            siteImageURL = ''
            try:
                siteImageURL = title.xpath('.//img/@src')[0]
                self.log('SEARCH:: Site Thumbnail Image URL: %s' % str(siteImageURL))
            except:
                self.log('SEARCH:: Error Site Thumbnail Image')
                pass

            # Site Released Date Check - default to filename year
            try:
                siteReleaseDate = datetime.datetime(int(siteURL.split('/')[4]), int(siteURL.split('/')[5]), int(siteURL.split('/')[6]))
            except:
                siteReleaseDate = compareReleaseDate
                self.log('SEARCH:: Error getting Site Release Date')
                pass

            timedelta = siteReleaseDate - compareReleaseDate
            self.log('SEARCH:: Compare Release Date - %s Site Date - %s : Dx [%s] days"', compareReleaseDate, siteReleaseDate, timedelta.days)
            if abs(timedelta.days) > 366:
                self.log('SEARCH:: Difference of more than a year between file date and %s date from Website')
                continue

            # we should have a match on both studio and title now
            results.Append(MetadataSearchResult(id = siteURL + '|' + siteImageURL, name = saveTitle, score = 100, lang = lang))

            # we have found a title that matches quit loop
            return

    def update(self, metadata, media, lang, force=True):
        folder, file = os.path.split(os.path.splitext(media.items[0].parts[0].file)[0])
        self.log('-----------------------------------------------------------------------')
        self.log('UPDATE:: Version - v.%s', VERSION_NO)
        self.log('UPDATE:: Platform - %s %s', platform.system(), platform.release())
        self.log('UPDATE:: File Name: %s', file)
        self.log('UPDATE:: Enclosing Folder: %s', folder)
        self.log('-----------------------------------------------------------------------')

        # Check filename format
        if not self.matchedFilename(file):
            self.log('UPDATE:: Skipping %s because the file name is not in the expected format: (Studio) - Title (Year)', file)
            return

        group_studio, group_title, group_year = self.getFilenameGroups(file)
        self.log('UPDATE:: Processing: Studio: %s   Title: %s   Year: %s', group_studio, group_title, group_year)

        # the ID is composed of the webpage for the video and its thumbnail
        html = HTML.ElementFromURL(metadata.id.split('|')[0], timeout=60, errors='ignore')

        #  The following bits of metadata need to be established and used to update the movie on plex
        #    1.  Metadata that is set by Agent as default
        #        a. Studio               : From studio group of filename - no need to process this as above
        #        b. Title                : From title group of filename - no need to process this as is used to find it on website
        #        c. Content Rating       : Always X
        #        d. Tag line             : Corresponds to the url of movie, retrieved from metadata.id split
        #        e. Originally Available : retrieved from the url of the movie
        #        f. background Art       : retrieved from metadata.id split
        #    2.  Metadata retrieved from website
        #        a. Summary 
        #        b. Cast                 : List of siteActors and Photos (alphabetic order) - Photos sourced from IAFD
        #        c. Poster

        # 1a.   Studio
        metadata.studio = group_studio
        self.log('UPDATE:: Studio: "%s"' % metadata.studio)

        # 1b.   Set Title
        metadata.title = group_title
        self.log('UPDATE:: Video Title: "%s"' % metadata.title)

        # 1c.   Set Content Rating to Adult
        metadata.content_rating = 'X'
        self.log('UPDATE:: Content Rating: X')

        # 1d.   Tagline
        metadata.tagline = metadata.id.split('|')[0]

        # 1e.   Originally Available At
        try:
            self.log('UPDATE:: Originally Available Date: Year [%s], Month [%s], Day [%s]',  metadata.id.split('/')[4], metadata.id.split('/')[5], metadata.id.split('/')[6])
            metadata.originally_available_at = datetime.datetime(int(metadata.id.split('/')[4]),int(metadata.id.split('/')[5]),int(metadata.id.split('/')[6])).date()
            metadata.year = metadata.originally_available_at.year
        except: 
            self.log('UPDATE:: Error setting Originally Available At from Filename')
            pass

        # 1f.   Background art
        arturl = metadata.id.split('|')[1].strip()
        if not arturl:
            validArtList = [arturl]
            if arturl not in metadata.art:
                try:
                    self.log('UPDATE:: Background Art URL: %s', arturl)
                    metadata.art[arturl] = Proxy.Preview(HTTP.Request(arturl).content, sort_order = 1)
                except:
                    self.log('UPDATE:: Error getting Background Art') 
                    pass
            #  clean up and only keep the background art we have added
            metadata.art.validate_keys(validArtList)

        # 2a.   Summary
        try:
            summary = html.xpath('//div[@class="entry-content"]')[0].text_content().strip()
            summary = re.sub('<[^<]+?>', '', summary)
            # delete first line from summary text as its the name of the video flick at studio
            # summary = summary[summary.index('\n')+1:]
            # ignore all code from start of html code
            self.log('UPDATE:: Summary Found: %s' %str(summary))
            if 'jQuery' in summary:
                summary = summary.split('jQuery')[0].strip()
            if '});' in summary:
                summary = summary.split('});')[1].strip()
            summary = summary.replace('Watch ' + group_title + ' at ' + group_studio, '').strip()
            summary = summary.replace('Watch as ' + group_title + ' at ' + group_studio, '').strip()
            summary = summary.replace(group_title + ' at ' + group_studio + ':', '').strip()
            metadata.summary = summary
        except:
            self.log('UPDATE:: Error getting Summary')
            pass

        # 2b.   Cast
        try:
            castdict = {}
            htmlcast = html.xpath('//a[contains(@href,"https://www.waybig.com/blog/tag/")]/text()')
            self.log('UPDATE:: Cast List %s', htmlcast)
            for castname in htmlcast:
                cast = castname.replace(u'\u2019s','').strip()
                if (len(cast) > 0):
                    castdict[cast] = self.getIAFDsiteActorImage(cast)

            # sort the dictionary and add kv to metadata
            metadata.roles.clear()
            for key in sorted (castdict): 
                role = metadata.roles.new()
                role.name = key
                role.photo = castdict[key]
        except:
            self.log('UPDATE:: Error getting Cast')
            pass

        # 2c.   Poster
        try:
            posterurl = html.xpath('//div[@class="entry-content"]/p/a[@target="_self" or @target="_blank"]/img/@src')[0]
            validPosterList = [posterurl]
            if posterurl not in metadata.posters:
                try:
                    self.log('UPDATE:: Movie Thumbnail Found: %s', posterurl)
                    metadata.posters[posterurl] = Proxy.Preview(HTTP.Request(posterurl).content, sort_order = 1)
                except:
                    self.log('UPDATE:: Error getting Poster') 
                    pass
            #  clean up and only keep the poster we have added
            metadata.posters.validate_keys(validPosterList)
        except:
            self.log('UPDATE:: Error getting Poster Art:')
            pass