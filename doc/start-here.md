About this service
------------------

Firstly, let's get the license question out of the way:

    All code in this repo is available for you to use under	the
	terms of the MIT license. Please review LICENSE for details.


Right. With that done, what is this service for and how do I set it up and run
it?

This service is designed to translate an Australian street address into a
Federal electoral division, and (where I've got the data for it) the
corresponding State division or district. Only lower houses of parliament or
assembly are covered - no Senate or Legislative Councils.

If you want to run this service yourself, you will need to provide a
configuration file `fmeconfig-prod.cfg` which contains the variable
`GMAPKEY` - your [Google Maps API key][gmapkey]. Protect this file with
appropriate locked down permissions, because that API service is a paid-for
thing.

Once you have that created, deploy it using your favourite method such as
those documented here under [Deployment Options][deployment options].


Data Files
----------

These reside in `find-my-electorate/json`, and are JSONified versions of
boundary data from the various Electoral Commissions. Some of that data has
come from KML files directly, and the rest has been transformed from ESRI
Shapefiles using [ogr2ogr][ogr2ogr]. The scripts to extract the required data
reside in my [grabbag][grabbag] repo.


Useful urls
-----------

To determine whether a given address is within an electorate, I've used the
example code for the [Even-Odd Rule][evenoddrule].

The [Google Maps API Developer Guide][gmapdocs] is very useful too.



Dependencies:
-------------

* [flask][Flask]
* [WTForms][WTForms]
* Python3 `json`
* Python3 `requests`


----

  [LICENSE]: ../LICENSE.md
  [gmapkey]: https://developers.google.com/maps/documentation/geocoding/get-api-key
  [flask]: http://flask.pocoo.org/
  [WTForms]: https://wtforms.readthedocs.io/en/stable/
  [deployment options]: http://flask.pocoo.org/docs/1.0/deploying/
  [ogr2ogr]: https://gdal.org/programs/ogr2ogr.html
  [grabbag]: https://github.com/jmcp/grabbag
  [evenoddrule]: https://en.wikipedia.org/wiki/Even%E2%80%93odd_rule
  [gmapdocs]: https://developers.google.com/maps/documentation/maps-static/dev-guide

