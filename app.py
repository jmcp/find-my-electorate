#!/usr/bin/env python3.8

#
# Copyright (c) 2019, 2020, James C. McPherson. All Rights Reserved.
#

# Available under the terms of the MIT license:
#
# Permission is hereby granted, free of charge, to any
# person obtaining a copy of this software and associated
# documentation files (the "Software"), to deal in the
# Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice
# shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
# KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
# WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
# OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import json
import requests


from base64 import b64encode

from flask import Flask, render_template, request

from os import environ

from urllib.parse import quote
from wtforms import Form, StringField


__doc__ = """

This is a Flask application. The user provides their street address,
which we turn into latitude/longitude and state using the Google Maps
API. We use this data in the PNPoly algorithm to determine which
federal, state or territory electorate it is part of, and report those
back to the user.

"""

usagestr = """

Run this from or with Flask.

"""


# Some global definitions
keyarg = "&key={gmapkey}"
queryurl = "https://maps.googleapis.com/maps/api/geocode/json?address="
queryurl += "{addr} Australia"
queryurl += keyarg

imgurl = "https://maps.googleapis.com/maps/api/staticmap?size=400x400"
imgurl += "&center={lati},{longi}&scale=1&maptype=roadmap&zoom=13"
imgurl += "&markers=X|{lati},{longi}"
imgurl += keyarg

# The formatted address we get back from the geocoding includes
# the word Australia so we don't need to append it here.
linkurl = "https://www.google.com.au/maps/place/{addr}"

aecurl = "https://www.aec.gov.au/profiles/{0}/{1}.htm"
stateurl = "https://en.wikipedia.org/wiki/Electoral_district_of_{0}"

stmap = {
    "ACT": "Australian Capital Territory",
    "NT": "Northern Territory",
    "NSW": "New South Wales",
    "QLD": "Queensland",
    "SA": "South Australia",
    "TAS": "Tasmania",
    "VIC": "Victoria",
    "WA": "Western Australia"
}

sturls = {
    "ACT": "https://en.wikipedia.org/wiki/{0}_electorate",
    "NT": "https://en.wikipedia.org/wiki/Electoral_division_of_{0}",
    "NSW": stateurl,
    "QLD": stateurl,
    "SA": stateurl,
    "TAS": "https://en.wikipedia.org/wiki/Division_of_{0}_(state)",
    "VIC": stateurl,
    "WA": stateurl
}

electoratejson = {}


class AddressForm(Form):
    address = StringField(label='Please enter your address')


# Helper functions
def get_geoJson(addr):
    """
    Queries the Google Maps API for specified address, returns
    a dict of the formatted address, the state/territory name, and
    a float-ified version of the latitude and longitude.
    """
    res = requests.get(queryurl.format(addr=addr, gmapkey=gmapkey))
    dictr = {}
    if res.json()["status"] == "ZERO_RESULTS" or not res.ok:
        dictr["res"] = res
    else:
        print(json.dumps(res.json(), indent=4))
        rresj = res.json()["results"][0]
        dictr["formatted_address"] = rresj["formatted_address"]
        dictr["latlong"] = rresj["geometry"]["location"]
        for el in rresj["address_components"]:
            if el["types"][0] == "administrative_area_level_1":
                dictr["state"] = el["short_name"]
    return dictr


# Let's provide a Google Maps static picture of the location
# Adapted from
# https://stackoverflow.com/questions/25140826/generate-image-embed-in-flask-with-a-data-uri/25141268#25141268
#
def get_image(latlong):
    """
    latlong -- a dict of the x and y coodinates of the location

    Returns a base64-encoded image
    """
    turl = imgurl.format(longi=latlong["lng"],
                         lati=latlong["lat"],
                         gmapkey=gmapkey)
    res = requests.get(turl)
    return b64encode(res.content)


# This is a slightly modified version of the example implementation
# provided at https://en.wikipedia.org/wiki/Even%E2%80%93odd_rule
def is_point_in_path(latlong, poly):
    """
    latlong -- a dict of the x and y coordinates of point
    poly    -- a list of tuples [(x, y), (x, y), ...]
    """
    x = latlong["lng"]
    y = latlong["lat"]
    num = len(poly)
    i = 0
    j = num - 1
    c = False
    for i in range(num):
        if ((poly[i][1] > y) != (poly[j][1] > y)) and \
           (x < poly[i][0] + (poly[j][0] - poly[i][0]) *
                (y - poly[i][1]) / (poly[j][1] - poly[i][1])):
            c = not c
        j = i
    return c


# Load the appropriate state/territory electorate kml
def load_kml(statename):
    """
    Loads a state/territory or federal electorate JSON file
    """
    fn = __name__ + "/json/{0}.json".format(statename)
    if statename not in electoratejson:
        # Not loaded yet
        with open(fn, "r") as infile:
            electoratejson[statename] = json.load(infile)


# Generate a list of federal divisions for the supplied state
# so that we reduce our search space.
def reduce_federal(state):
    """Returns a list of federal divisions for the given state"""
    divlist = []
    fedj = electoratejson["FEDERAL"]
    for division in fedj:
        if fedj[division]["jurisdiction"] == state:
            divlist.append(division)
    return divlist


#
# boilerplate and basic setup
app = Flask("find-my-electorate")
gmapkey = environ["GMAPKEY"]

# Set up the federal part, we handle the state part when we have
# a state to query.
load_kml("FEDERAL")


@app.route("/results", methods=('POST',))
def results():
    dictr = get_geoJson(request.form["address"])
    if "res" in dictr:
        # Error case - didn't get 200 from the external query
        return render_template("not-200.html",
                               address=request.form["address"],
                               result=dictr["res"],
                               content=dictr["res"].json())

    nation = dictr["formatted_address"].split(",")[-1].strip()
    if nation != "Australia":
        # Error - not an Australian address
        return render_template("not-au.html",
                               address=dictr["formatted_address"])

    # debugging
    # print(dictr)

    isSupported = True
    load_kml(dictr["state"])

    # Perform the actual check for which federal and state/territory
    # electorate this lat/long is in. Courtesy of Section 29 of the
    # Australian Constitution, federal divisions may NOT cross state
    # or territory boundaries. That helps reduce our division search
    # a little.
    feddiv = ""
    statediv = ""

    # Grab a small (400x400) static image of the location
    img_data = get_image(dictr["latlong"])
    # A convenience assignment
    fedj = electoratejson["FEDERAL"]
    for division in reduce_federal(dictr["state"]):
        if is_point_in_path(dictr["latlong"], fedj[division]["coords"]):
            feddiv = division
            break

    statej = electoratejson[dictr["state"]]
    for division in statej:
        # print("checking against {division}".format(division=division))
        if is_point_in_path(dictr["latlong"], statej[division]["coords"]):
            statediv = division
            break
    if statediv == "":
        # print("Unable to find a match for {formattedaddr} in "
        #       "{statej}".format(
        #       formattedaddr=dictr["formatted_address"], statej=statej))
        isSupported = False

    return render_template("results.html",
                           address=dictr["formatted_address"],
                           feddiv=feddiv,
                           statediv=statediv,
                           StateOrTerritoryName=stmap[dictr["state"]],
                           isSupported=isSupported,
                           aecurl=aecurl.format(dictr["state"].lower(),
                                                feddiv.lower()),
                           sturl=sturls[dictr["state"]].format(
                               statediv.replace(" ", "_")),
                           img_data=format(quote(img_data)),
                           linkurl=linkurl.format(
                               addr=dictr["formatted_address"]
                           ).replace(" ", "+"))


@app.route("/")
def index():
    form = AddressForm()
    return render_template("index.html", form=form)
