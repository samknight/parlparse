# vim:sw=8:ts=8:et:nowrap
# -*- coding: latin-1 -*-

import string
import re
import xml.sax

titleconv = {  'L.':'Lord',
			   'B.':'Baroness',
			   'Abp.':'Archbishop',
			   'Bp.':'Bishop',
			   'V.':'Viscount',
			   'E.':'Earl',
			   'D.':'Duke',
			   'M.':'Marquess',
			   'C.':'Countess',
			   'Ly.':'Lady',
			}

# more tedious stuff to do: "earl of" and "sitting as" cases

hontitles = [ 'Lord  ?Bishop', 'Lord', 'Baroness', 'Viscount', 'Earl', 'Countess', 'Archbishop', 'Duke', 'Lady' ]
hontitleso = string.join(hontitles, '|')

honcompl = re.compile('(?:The\s+(%s)|(%s) \s*(.*?))(?:\s+of\s+(.*))?$' % (hontitleso, hontitleso))


class LordsList(xml.sax.handler.ContentHandler):
	def __init__(self):
		self.lords={} # ID --> MPs
		self.lordnames={} # "lordnames" --> lords
		self.parties = {} # constituency --> MPs

		parser = xml.sax.make_parser()
		parser.setContentHandler(self)

		parser.parse("../members/peers-ucl.xml")
		#parser.parse("../members/lordnametoofname.xml")

		# set this to the file if we are to divert unmatched names into a file
		# for collection
		self.newlordsdumpfname = "../members/newlordsdump.xml"
		# self.newlordsdumpfname = None  # suppresses the feature
		self.newlordsdumpfile = None  # file opens only on first use
		self.newlordsdumped = [ ]

	# check that the lordofnames that are blank happen after the ones that have values
	# where the lordname matches
	def startElement(self, name, attr):
		""" This handler is invoked for each XML element (during loading)"""
		#id="uk.org.publicwhip/lord/100001"
		#house="lords"
		#forenames="Morys"
		#title="Lord" lordname="Aberdare" lordofname=""
		#peeragetype="HD" affiliation="Con"
		#fromdate="1957" todate="2005-01-23"

		if name == "lord":
			if self.lords.get(attr["id"]):
				raise Exception, "Repeated identifier %s in members XML file" % attr["id"]

			# needs to make a copy into a map because entries can't be rewritten
			cattr = { "id":attr["id"],
					  "title":attr["title"], "lordname":attr["lordname"], "lordofname":attr["lordofname"],
					  "fromdate":attr["fromdate"], "todate":attr["todate"] }
			self.lords[attr["id"]] = cattr

			lname = attr["lordname"] or attr["lordofname"]
			lname = re.sub("\.", "", lname)
			assert lname
			self.lordnames.setdefault(lname, []).append(cattr)

		#<lordnametoofname id="uk.org.publicwhip/lord/100415" title="Earl" name="Mar and Kellie">
		elif name == "lordnametoofname":
			lm = self.lords[attr["id"]]
			assert lm["title"] == attr["title"]
			assert not lm["lordofname"]
			assert lm["lordname"] == attr["name"]
			lm["lordofname"] = lm["lordname"]
			lm["lordname"] = ""

		else:
			assert name == "publicwhip"


	# call this when the ofname info is discovered to be incorrect
	def DumpCrossovername(self, lm, stampurl):
		assert IsNotQuiet()
		assert lm["lordname"]
		assert not lm["lordofname"]
		assert self.newlordsdumpfname
		if not self.newlordsdumpfile:
			print "Opening", self.newlordsdumpfname
			self.newlordsdumpfile = open(self.newlordsdumpfname, "w")

		# dump new names to a file
		if lm["id"] not in self.newlordsdumped:
			print "Dumping:", (lm["id"], lm["lordname"], lm["lordofname"])
			self.newlordsdumpfile.write('<lordnametoofname id="%s" title="%s" name="%s"/>\n' % (lm["id"], lm["title"], lm["lordname"]))
			self.newlordsdumpfile.flush()
			self.newlordsdumped.append(lm["id"])


	# main matchinf function
	def GetLordID(self, ltitle, llordname, llordofname, loffice, stampurl, sdate, bDivision):
		if ltitle == "Lord Bishop":
			ltitle = "Bishop"

		llordofname = string.replace(llordofname, ".", "")
		llordname = string.replace(llordname, ".", "")
		llordname = string.replace(llordname, "&#039;", "'")

		# got bored with fixing this example
		if (llordname, llordofname) == ("Mackay", "Ardbrecknish"):
			llordname = "MacKay"

                # TODO: Need a Lords version of member-aliases.xml I guess
                if ltitle == "Bishop" and llordofname == "Southwell" and sdate>='2005-07-01':
                        llordofname = "Southwell and Nottingham"
                if ltitle == "Bishop" and llordname == "Southwell" and sdate>='2005-07-01':
                        llordname = "Southwell and Nottingham"

		lname = llordname or llordofname
		assert lname
		lmatches = self.lordnames.get(lname, [])

		# match to successive levels of precision for identification
		res = [ ]
		for lm in lmatches:
			if lm["title"] != ltitle:  # mismatch title
				continue
			if llordname and llordofname: # two name case
				if (lm["lordname"] == llordname) and (lm["lordofname"] == llordofname):
					if lm["fromdate"] <= sdate <= lm["todate"]:
						res.append(lm)
					else:
						raise ContextException("lord not matching date range", stamp=stampurl, fragment=llordname)
				continue

			# skip onwards if we have a double name
			if lm["lordname"] and lm["lordofname"]:
				continue

			# single name cases (name and of-name)
			# this is the case where they correspond (both names, or both of-names) correctly
			lmlname = lm["lordname"] or lm["lordofname"]
			if (llordname and lm["lordname"]) or (llordofname and lm["lordofname"]):
				if lname == lmlname:
					if lm["fromdate"] <= sdate <= lm["todate"]:
						res.append(lm)

					# the only case of repeated use of name for different people is with Bishops,
					# and the date range will determin which person the bishop was
					elif ltitle != "Bishop" and ltitle != "Archbishop" and (ltitle, lname) != ("Duke", "Norfolk"):
						print "cm---", ltitle, llordname, llordofname, lm["fromdate"], lm["todate"]
						raise ContextException("lord not matching date range", stamp=stampurl, fragment=lname)
				continue

			# cross-match
			if lname == lmlname:
				if lm["fromdate"] <= sdate <= lm["todate"]:
					if lm["lordname"] and llordofname:
						#if not IsNotQuiet():
						raise ContextException("lordofname matches lordname in lordlist", stamp=stampurl, fragment=lname)
						print "cm---", ltitle, lm["lordname"], lm["lordofname"], llordname, llordofname
						self.DumpCrossovername(lm, stampurl)  # save into file which we will use (when complete, this line will become an assert False)
					else:
						assert lm["lordofname"] and llordname
						# of-name distinction lost in division lists
						if not bDivision:
							raise ContextException("lordname matches lordofname in lordlist", stamp=stampurl, fragment=lname)
					res.append(lm)
				elif ltitle != "Bishop" and ltitle != "Archbishop" and (ltitle, lname) != ("Duke", "Norfolk"):
					print lm
					raise ContextException("wrong dates on lords with same name", stamp=stampurl, fragment=lname)

		if not res:
			print "Unknown Lord", (ltitle, llordname, llordofname, stampurl)
			raise ContextException("unknown lord", stamp=stampurl, fragment=lname)

		assert len(res) == 1
		return res[0]["id"]


	def GetLordIDfname(self, name, loffice, sdate, stampurl=None):
		if re.match("Lord Bishop ", name):
			name = "The " + name

		hom = honcompl.match(name)
		if not hom:
			print "format failure on '" + name + "'"
			raise ContextException("lord name format failure", stamp=stampurl, fragment=name)

		# now we have a speaker, try and break it up
		ltit = hom.group(1)
		if not ltit:
			ltit = hom.group(2)
			lname = hom.group(3)
		else:
			lname = ""

		ltit = re.sub("  ", " ", ltit)
		lplace = ""
		if hom.group(4):
			lplace = re.sub("  ", " ", hom.group(4))

		lname = re.sub("^De ", "de ", lname)

		return self.GetLordID(ltit, lname, lplace, loffice, stampurl, sdate, False)


	def MatchRevName(self, fss, sdate, stampurl):
		assert fss
		lfn = re.match('(.*?)(?: of (.*?))?, ?((?:L|B|Abp|Bp|V|E|D|M|C|Ly)\.?)$', fss)
		if not lfn:
			print "$$$%s$$$" % fss
			raise ContextException("No match of format in MatchRevName", stamp=stampurl, fragment=fss)
		shorttitle = lfn.group(3)
		if shorttitle[-1] != '.':
			shorttitle += "."
		ltitle = titleconv[shorttitle]
		llordname = string.replace(lfn.group(1), ".", "")
		llordname = string.replace(llordname, "&#039;", "'")
		llordname = re.sub("^De ", "de ", llordname)
		llordofname = ""
		if lfn.group(2):
			llordofname = string.replace(lfn.group(2), ".", "")

		return self.GetLordID(ltitle, llordname, llordofname, "", stampurl, sdate, True)


# Construct the global singleton of class which people will actually use
lordsList = LordsList()


