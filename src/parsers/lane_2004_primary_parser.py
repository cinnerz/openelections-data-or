#!/usr/bin/python
# -*- coding: utf-8 -*-

# The MIT License (MIT)
# Copyright (c) 2016 Nick Kocharhook
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
# SOFTWARE.

import re
import os
import sys
import pdb
import fileinput
import unicodecsv
import pprint

# Configure variables
county = 'Lane'
outfile = '20040518__or__primary__lane__precinct.csv'


headers = ['county', 'precinct', 'office', 'district', 'party', 'candidate', 'votes']
party_prefixes = ['DEM', 'REP']

office_lookup = {
	'U S PRESIDENT': 'President',
	'UNITED STATES SENATOR': 'U.S. Senate',
	'REP IN CONGRESS': 'U.S. House',
	'SECRETARY OF STATE': 'Secretary of State',
	'STATE TREASURER': 'State Treasurer',
	'ATTORNEY GENERAL': 'Attorney General',
	'GOVERNOR': 'Governor',
	'STATE REPRESENTATIVE': 'State House',
	'SENATOR': 'State Senate'
}

candidate_lookup = {
	'WRITE-IN': 'Write-in',
	'OVER VOTES': 'Over Votes',
	'UNDER VOTES': 'Under Votes'
}


def main():
	currentCanvass = ""
	allCanvasses = []
	divisionRE = re.compile(" PAGE ")

	# read from stdin
	for line in sys.stdin.readlines():
		if divisionRE.search(line):
			canvasses = preprocessPage(currentCanvass)

			for office in canvasses:
				if office:
					canvass = OfficeCanvass(office)
					if canvass.office in office_lookup: # exclude lower offices
						allCanvasses.append(canvass)

				# pdb.set_trace()

			currentCanvass = ""
		else:
			currentCanvass += line

	# printCanvasses(allCanvasses)
	writeCSV(allCanvasses)

def preprocessPage(page):
	outCanvasses = [[],[]]

	for line in page.splitlines():
		columns = line.split("\xb3")

		if len(columns) == 1: # no results info on this line
			continue
		if len(columns) == 5: # if there are 2 offices
			outCanvasses[1].append(columns[0]+columns[3])

		# there will always be at least 1 office
		outCanvasses[0].append(columns[0]+columns[2])

	if not outCanvasses[1]:
		del(outCanvasses[1])

	return outCanvasses


def writeCSV(allCanvasses):
	def listGet(inList, index, default):
		try:
			out = inList[index]
		except IndexError:
			out = default

		return out

	with open(outfile, 'wb') as csvfile:
		w = unicodecsv.writer(csvfile, encoding='utf-8')
		w.writerow(headers)

		for canvass in allCanvasses:
			for precinct, results in canvass.results.iteritems():
				for index, result in enumerate(results):
					normalisedOffice = office_lookup[canvass.office] # Normalise the office
					candidate = canvass.candidates[index]
					normalisedCandidate = candidate_lookup.get(candidate, candidate.title()) # Normalise the candidate

					row = [county, precinct, normalisedOffice, canvass.district,
							canvass.party, normalisedCandidate, result]

					print row
					w.writerow(row)

def printCanvasses(allCanvasses):
	pp = pprint.PrettyPrinter(indent=4, width=100)

	for canvass in allCanvasses:
		print canvass.party
		print canvass.office
		print canvass.district
		print canvass.candidates
		pp.pprint(canvass.results)
		print "====="



class OfficeCanvass(object):
	def __init__(self, lines):
		# pp = pprint.PrettyPrinter(indent=4)
		# pp.pprint(lines)

		self.lines = lines #text.split('\r\n') # File uses Windows line endings
		self.header = []
		self.table = []
		self.results = {}
		self.district = ""
		self.party = ""
		self.candidates = []

		self.hyphenRE = re.compile("(\xc4\xc4+)")
		self.endOfTableRE = re.compile("OFFICIAL CANVASS|TOTALS")
		self.districtRE = re.compile(",? (\d\d?)\w?\w? DIST(RICT)?")
		self.precintRE = re.compile("\d\d? PRECINCTS")
		self.turnoutRE = re.compile("\xb3[^\xb3]+\xb3")

		self.removeTurnoutColumns()
		self.parseTitle()
		self.parseOfficePartyDistrict()
		self.populateHeaderAndTable()
		self.parseHeader()
		self.parseResults()

	def __repr__(self):
		return self.title+self.party+self.office

	def removeTurnoutColumns(self):
		for index, line in enumerate(self.lines):
			m = self.turnoutRE.search(line)
			if m:
				self.lines[index] = line.replace(m.group(0), "")

	def parseTitle(self):
		self.title = self.lines[0].strip()
		
	def parseOfficePartyDistrict(self):
		prefix = self.title[0:3]
		self.office = self.title

		if prefix in party_prefixes:
			self.party = prefix
			self.office = self.title[4:] # Remove party from office

		m = self.districtRE.search(self.office)
		if m:
			self.district = m.group(1).lstrip("0")
			self.office = self.office.replace(m.group(0), "") # Remove district from office

	def populateHeaderAndTable(self):
		inTable = False

		for line in self.lines[2:]:
			if not inTable:
				self.header.append(line)
				if self.hyphenRE.search(line):
					inTable = True
			else:
				if self.endOfTableRE.search(line):
					break

				if len(line.strip()):
					self.table.append(line)

	def parseHeader(self):
		headerLines = self.header

		# 1. Remove the precinct count
		lastLine = headerLines[-2]
		m = self.precintRE.search(lastLine)

		if m:
			lastLine = lastLine.replace(m.group(0), " "*len(m.group(0)))
			headerLines[-2] = lastLine

		# 2. Find out where the columns are
		cols = []
		longestString = len(headerLines[-1])

		for m in self.hyphenRE.finditer(headerLines[-1]):
			if len(m.group(0)) == 5: # Skip the first set of hyphens
				for i, g in enumerate(m.groups()):
					cols.append(m.span(i))

		# 3. Make sure all strings are the same length
		for i, line in enumerate(headerLines):
			headerLines[i] = headerLines[i].ljust(longestString)

		# 4. Create 2D array of characters to easily zip()
		bitmap = []
		for line in headerLines[:-1]: #skip line of hyphens
			bitmap.append(list(line))

		# for aList in bitmap:
		# 	print aList

		# 5. Read vertical columns of characters as the names, removing unused spaces
		names = []
		for i, col in enumerate(cols):
			name = ""
			for colNum in range(col[0], col[1]):
				name += "".join(zip(*bitmap)[colNum]) + " "
			names.append(" ".join(name.split()))

		self.candidates = names

	def parseResults(self):
		for line in self.table:
			columns = line.split()
			candidateCount = len(self.candidates)

			votes = columns[-candidateCount:]
			del(columns[-candidateCount:])
			
			precinct = " ".join(columns)
			self.results[precinct] = votes



# Default function is main()
if __name__ == '__main__':
	main()