#!/usr/bin/env python3.7

#
# Copyright (c) 2019, James C. McPherson. All Rights Reserved.
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

from flask import Flask, render_template, request
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
queryurl = "https://maps.googleapis.com/maps/api/geocode/json?address="
queryurl += "{addr} Australia&key={gmapkey}"

aecurl = "https://www.aec.gov.au/profiles/{0}/{1}.htm"
stateurl = "https://en.wikipedia.org/wiki/Electoral_district_of_{0}"

# We don't have support for all the jurisdictions in the country
# *yet*, so keep a whitelist of those we know about so we can
# handle out-of-bounds cases politely.
supported = {"FEDERAL", "QLD", "NSW", "VIC", "TAS"}
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
    if not res.ok:
        dictr["res"] = res
    else:
        rresj = res.json()["results"][0]
        dictr["formatted_address"] = rresj["formatted_address"]
        dictr["latlong"] = rresj["geometry"]["location"]
        for el in rresj["address_components"]:
            if el["types"][0] == "administrative_area_level_1":
                dictr["state"] = el["short_name"]
    return dictr


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
app.config.from_pyfile("fmeconfig-prod.cfg")
gmapkey = app.config["GMAPKEY"]

# Set up the federal part, we handle the state part when we have
# a state to query.
load_kml("FEDERAL")


@app.route("/results", methods=('POST',))
def results():
    dictr = get_geoJson(request.form["address"])
    if "res" in dictr:
        # Error case - didn't get 200 from the external query
        print(dir(dictr["res"]))
        return render_template("not-200.html",
                               address=request.form["address"],
                               result=dictr["res"])

    nation = dictr["formatted_address"].split(",")[-1].strip()
    if nation != "Australia":
        # Error - not an Australian address
        return render_template("not-au.html",
                               address=dictr["formatted_address"])

    isSupported = False
    if dictr["state"] in supported:
        load_kml(dictr["state"])
        isSupported = True

    # Perform the actual check for which federal and state/territory
    # electorate this lat/long is in. Courtesy of Section 29 of the
    # Australian Constitution, federal divisions may NOT cross state
    # or territory boundaries. That helps reduce our division search
    # a little.
    feddiv = ""
    statediv = ""

    # A convenience assignment
    fedj = electoratejson["FEDERAL"]
    for division in reduce_federal(dictr["state"]):
        if is_point_in_path(dictr["latlong"], fedj[division]["coords"]):
            feddiv = division
            break

    if dictr["state"] in supported:
        statej = electoratejson[dictr["state"]]
        for division in statej:
            if is_point_in_path(dictr["latlong"], statej[division]["coords"]):
                statediv = division
                break

    return render_template("results.html",
                           address=dictr["formatted_address"],
                           feddiv=feddiv,
                           statediv=statediv,
                           StateOrTerritoryName=stmap[dictr["state"]],
                           isSupported=isSupported,
                           aecurl=aecurl.format(dictr["state"].lower(),
                                                feddiv.lower()),
                           sturl=sturls[dictr["state"]].format(
                               statediv.replace(" ", "_")))


@app.route("/")
def index():
    form = AddressForm()
    return render_template("index.html", form=form)
