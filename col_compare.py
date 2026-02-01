#!/usr/bin/env python3
"""Cost of Living Comparison Tool.

Fetches living wage data from MIT's Living Wage Calculator and compares
US metro areas, counties, or states across all expense categories.

Data source: https://livingwage.mit.edu
Usage is within their stated 10-location fair-use policy.
"""

import argparse
import math
import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Location database: ~50 major metros (CBSA code -> name) and 50 states + DC
# ---------------------------------------------------------------------------

METROS = {
    "10180": "Abilene, TX",
    "10420": "Akron, OH",
    "10500": "Albany, GA",
    "10540": "Albany-Lebanon, OR",
    "10580": "Albany-Schenectady-Troy, NY",
    "10740": "Albuquerque, NM",
    "10780": "Alexandria, LA",
    "10900": "Allentown-Bethlehem-Easton, PA",
    "11020": "Altoona, PA",
    "11100": "Amarillo, TX",
    "11180": "Ames, IA",
    "11260": "Anchorage, AK",
    "11460": "Ann Arbor, MI",
    "11500": "Anniston-Oxford, AL",
    "11540": "Appleton, WI",
    "11700": "Asheville, NC",
    "12020": "Athens-Clarke County, GA",
    "12060": "Atlanta-Sandy Springs-Alpharetta, GA",
    "12100": "Atlantic City-Hammonton, NJ",
    "12220": "Auburn-Opelika, AL",
    "12260": "Augusta-Richmond County, GA",
    "12420": "Austin-Round Rock-Georgetown, TX",
    "12540": "Bakersfield, CA",
    "12580": "Baltimore-Columbia-Towson, MD",
    "12620": "Bangor, ME",
    "12700": "Barnstable Town, MA",
    "12940": "Baton Rouge, LA",
    "12980": "Battle Creek, MI",
    "13020": "Bay City, MI",
    "13140": "Beaumont-Port Arthur, TX",
    "13220": "Beckley, WV",
    "13380": "Bellingham, WA",
    "13460": "Bend, OR",
    "13740": "Billings, MT",
    "13780": "Binghamton, NY",
    "13820": "Birmingham-Hoover, AL",
    "13900": "Bismarck, ND",
    "13980": "Blacksburg-Christiansburg, VA",
    "14010": "Bloomington, IL",
    "14020": "Bloomington, IN",
    "14100": "Bloomsburg-Berwick, PA",
    "14260": "Boise City, ID",
    "14460": "Boston-Cambridge-Newton, MA",
    "14500": "Boulder, CO",
    "14540": "Bowling Green, KY",
    "14740": "Bremerton-Silverdale-Port Orchard, WA",
    "14860": "Bridgeport-Stamford-Norwalk, CT",
    "15180": "Brownsville-Harlingen, TX",
    "15260": "Brunswick, GA",
    "15380": "Buffalo-Cheektowaga, NY",
    "15500": "Burlington, NC",
    "15540": "Burlington-South Burlington, VT",
    "15680": "California-Lexington Park, MD",
    "15940": "Canton-Massillon, OH",
    "15980": "Cape Coral-Fort Myers, FL",
    "16020": "Cape Girardeau, MO",
    "16060": "Carbondale-Marion, IL",
    "16180": "Carson City, NV",
    "16220": "Casper, WY",
    "16300": "Cedar Rapids, IA",
    "16540": "Chambersburg-Waynesboro, PA",
    "16580": "Champaign-Urbana, IL",
    "16620": "Charleston, WV",
    "16700": "Charleston-North Charleston, SC",
    "16740": "Charlotte-Concord-Gastonia, NC",
    "16820": "Charlottesville, VA",
    "16860": "Chattanooga, TN",
    "16940": "Cheyenne, WY",
    "16980": "Chicago-Naperville-Elgin, IL",
    "17020": "Chico, CA",
    "17140": "Cincinnati, OH",
    "17300": "Clarksville, TN",
    "17420": "Cleveland, TN",
    "17460": "Cleveland-Elyria, OH",
    "17660": "Coeur d'Alene, ID",
    "17780": "College Station-Bryan, TX",
    "17820": "Colorado Springs, CO",
    "17860": "Columbia, MO",
    "17900": "Columbia, SC",
    "17980": "Columbus, GA",
    "18020": "Columbus, IN",
    "18140": "Columbus, OH",
    "18580": "Corpus Christi, TX",
    "18700": "Corvallis, OR",
    "18880": "Crestview-Fort Walton Beach-Destin, FL",
    "19060": "Cumberland, MD",
    "19100": "Dallas-Fort Worth-Arlington, TX",
    "19140": "Dalton, GA",
    "19180": "Danville, IL",
    "19300": "Daphne-Fairhope-Foley, AL",
    "19340": "Davenport-Moline-Rock Island, IA",
    "19430": "Dayton-Kettering, OH",
    "19460": "Decatur, AL",
    "19500": "Decatur, IL",
    "19660": "Deltona-Daytona Beach-Ormond Beach, FL",
    "19740": "Denver-Aurora-Lakewood, CO",
    "19780": "Des Moines-West Des Moines, IA",
    "19820": "Detroit-Warren-Dearborn, MI",
    "20020": "Dothan, AL",
    "20100": "Dover, DE",
    "20220": "Dubuque, IA",
    "20260": "Duluth, MN",
    "20500": "Durham-Chapel Hill, NC",
    "20700": "East Stroudsburg, PA",
    "20740": "Eau Claire, WI",
    "20940": "El Centro, CA",
    "21060": "Elizabethtown-Fort Knox, KY",
    "21140": "Elkhart-Goshen, IN",
    "21300": "Elmira, NY",
    "21340": "El Paso, TX",
    "21420": "Enid, OK",
    "21500": "Erie, PA",
    "21660": "Eugene-Springfield, OR",
    "21780": "Evansville, IN",
    "21820": "Fairbanks, AK",
    "22020": "Fargo, ND",
    "22140": "Farmington, NM",
    "22180": "Fayetteville, NC",
    "22220": "Fayetteville-Springdale-Rogers, AR",
    "22380": "Flagstaff, AZ",
    "22420": "Flint, MI",
    "22500": "Florence, SC",
    "22520": "Florence-Muscle Shoals, AL",
    "22540": "Fond du Lac, WI",
    "22660": "Fort Collins, CO",
    "22900": "Fort Smith, AR",
    "23060": "Fort Wayne, IN",
    "23420": "Fresno, CA",
    "23460": "Gadsden, AL",
    "23540": "Gainesville, FL",
    "23580": "Gainesville, GA",
    "23900": "Gettysburg, PA",
    "24020": "Glens Falls, NY",
    "24140": "Goldsboro, NC",
    "24220": "Grand Forks, ND",
    "24260": "Grand Island, NE",
    "24300": "Grand Junction, CO",
    "24340": "Grand Rapids-Kentwood, MI",
    "24420": "Grants Pass, OR",
    "24500": "Great Falls, MT",
    "24540": "Greeley, CO",
    "24580": "Green Bay, WI",
    "24660": "Greensboro-High Point, NC",
    "24780": "Greenville, NC",
    "24860": "Greenville-Anderson, SC",
    "25060": "Gulfport-Biloxi, MS",
    "25180": "Hagerstown-Martinsburg, MD",
    "25220": "Hammond, LA",
    "25260": "Hanford-Corcoran, CA",
    "25420": "Harrisburg-Carlisle, PA",
    "25500": "Harrisonburg, VA",
    "25540": "Hartford-East Hartford-Middletown, CT",
    "25620": "Hattiesburg, MS",
    "25860": "Hickory-Lenoir-Morganton, NC",
    "25940": "Hilton Head Island-Bluffton, SC",
    "25980": "Hinesville, GA",
    "26140": "Homosassa Springs, FL",
    "26300": "Hot Springs, AR",
    "26380": "Houma-Thibodaux, LA",
    "26420": "Houston-The Woodlands-Sugar Land, TX",
    "26580": "Huntington-Ashland, WV",
    "26620": "Huntsville, AL",
    "26820": "Idaho Falls, ID",
    "26900": "Indianapolis-Carmel-Anderson, IN",
    "26980": "Iowa City, IA",
    "27060": "Ithaca, NY",
    "27100": "Jackson, MI",
    "27140": "Jackson, MS",
    "27180": "Jackson, TN",
    "27260": "Jacksonville, FL",
    "27340": "Jacksonville, NC",
    "27500": "Janesville-Beloit, WI",
    "27620": "Jefferson City, MO",
    "27740": "Johnson City, TN",
    "27780": "Johnstown, PA",
    "27860": "Jonesboro, AR",
    "27900": "Joplin, MO",
    "27980": "Kahului-Wailuku-Lahaina, HI",
    "28020": "Kalamazoo-Portage, MI",
    "28100": "Kankakee, IL",
    "28140": "Kansas City, MO",
    "28420": "Kennewick-Richland, WA",
    "28660": "Killeen-Temple, TX",
    "28700": "Kingsport-Bristol, TN",
    "28740": "Kingston, NY",
    "28940": "Knoxville, TN",
    "29020": "Kokomo, IN",
    "29100": "La Crosse-Onalaska, WI",
    "29180": "Lafayette, LA",
    "29200": "Lafayette-West Lafayette, IN",
    "29340": "Lake Charles, LA",
    "29420": "Lake Havasu City-Kingman, AZ",
    "29460": "Lakeland-Winter Haven, FL",
    "29540": "Lancaster, PA",
    "29620": "Lansing-East Lansing, MI",
    "29700": "Laredo, TX",
    "29740": "Las Cruces, NM",
    "29820": "Las Vegas-Henderson-Paradise, NV",
    "29940": "Lawrence, KS",
    "30020": "Lawton, OK",
    "30140": "Lebanon, PA",
    "30300": "Lewiston, ID",
    "30340": "Lewiston-Auburn, ME",
    "30460": "Lexington-Fayette, KY",
    "30620": "Lima, OH",
    "30700": "Lincoln, NE",
    "30780": "Little Rock-North Little Rock-Conway, AR",
    "30860": "Logan, UT",
    "30980": "Longview, TX",
    "31020": "Longview, WA",
    "31080": "Los Angeles-Long Beach-Anaheim, CA",
    "31140": "Louisville/Jefferson County, KY",
    "31180": "Lubbock, TX",
    "31340": "Lynchburg, VA",
    "31420": "Macon-Bibb County, GA",
    "31460": "Madera, CA",
    "31540": "Madison, WI",
    "31700": "Manchester-Nashua, NH",
    "31740": "Manhattan, KS",
    "31860": "Mankato, MN",
    "31900": "Mansfield, OH",
    "32580": "McAllen-Edinburg-Mission, TX",
    "32780": "Medford, OR",
    "32820": "Memphis, TN",
    "32900": "Merced, CA",
    "33100": "Miami-Fort Lauderdale-Pompano Beach, FL",
    "33140": "Michigan City-La Porte, IN",
    "33220": "Midland, MI",
    "33260": "Midland, TX",
    "33340": "Milwaukee-Waukesha, WI",
    "33460": "Minneapolis-St. Paul-Bloomington, MN",
    "33540": "Missoula, MT",
    "33660": "Mobile, AL",
    "33700": "Modesto, CA",
    "33740": "Monroe, LA",
    "33780": "Monroe, MI",
    "33860": "Montgomery, AL",
    "34060": "Morgantown, WV",
    "34100": "Morristown, TN",
    "34580": "Mount Vernon-Anacortes, WA",
    "34620": "Muncie, IN",
    "34740": "Muskegon, MI",
    "34820": "Myrtle Beach-Conway-North Myrtle Beach, SC",
    "34900": "Napa, CA",
    "34940": "Naples-Marco Island, FL",
    "34980": "Nashville-Davidson--Murfreesboro--Franklin, TN",
    "35100": "New Bern, NC",
    "35300": "New Haven-Milford, CT",
    "35380": "New Orleans-Metairie, LA",
    "35620": "New York-Newark-Jersey City, NY",
    "35660": "Niles, MI",
    "35840": "North Port-Sarasota-Bradenton, FL",
    "35980": "Norwich-New London, CT",
    "36100": "Ocala, FL",
    "36140": "Ocean City, NJ",
    "36220": "Odessa, TX",
    "36260": "Ogden-Clearfield, UT",
    "36420": "Oklahoma City, OK",
    "36500": "Olympia-Lacey-Tumwater, WA",
    "36540": "Omaha-Council Bluffs, NE",
    "36740": "Orlando-Kissimmee-Sanford, FL",
    "36780": "Oshkosh-Neenah, WI",
    "36980": "Owensboro, KY",
    "37100": "Oxnard-Thousand Oaks-Ventura, CA",
    "37340": "Palm Bay-Melbourne-Titusville, FL",
    "37460": "Panama City, FL",
    "37620": "Parkersburg-Vienna, WV",
    "37860": "Pensacola-Ferry Pass-Brent, FL",
    "37900": "Peoria, IL",
    "37980": "Philadelphia-Camden-Wilmington, PA",
    "38060": "Phoenix-Mesa-Chandler, AZ",
    "38220": "Pine Bluff, AR",
    "38300": "Pittsburgh, PA",
    "38340": "Pittsfield, MA",
    "38540": "Pocatello, ID",
    "38860": "Portland-South Portland, ME",
    "38900": "Portland-Vancouver-Hillsboro, OR",
    "38940": "Port St. Lucie, FL",
    "39100": "Poughkeepsie-Newburgh-Middletown, NY",
    "39150": "Prescott Valley-Prescott, AZ",
    "39300": "Providence-Warwick, RI",
    "39340": "Provo-Orem, UT",
    "39380": "Pueblo, CO",
    "39460": "Punta Gorda, FL",
    "39540": "Racine, WI",
    "39580": "Raleigh-Cary, NC",
    "39660": "Rapid City, SD",
    "39740": "Reading, PA",
    "39820": "Redding, CA",
    "39900": "Reno, NV",
    "40060": "Richmond, VA",
    "40140": "Riverside-San Bernardino-Ontario, CA",
    "40220": "Roanoke, VA",
    "40340": "Rochester, MN",
    "40380": "Rochester, NY",
    "40420": "Rockford, IL",
    "40580": "Rocky Mount, NC",
    "40660": "Rome, GA",
    "40900": "Sacramento-Roseville-Folsom, CA",
    "40980": "Saginaw, MI",
    "41060": "St. Cloud, MN",
    "41100": "St. George, UT",
    "41140": "St. Joseph, MO",
    "41180": "St. Louis, MO",
    "41420": "Salem, OR",
    "41500": "Salinas, CA",
    "41540": "Salisbury, MD",
    "41620": "Salt Lake City, UT",
    "41660": "San Angelo, TX",
    "41700": "San Antonio-New Braunfels, TX",
    "41740": "San Diego-Chula Vista-Carlsbad, CA",
    "41860": "San Francisco-Oakland-Berkeley, CA",
    "41940": "San Jose-Sunnyvale-Santa Clara, CA",
    "42020": "San Luis Obispo-Paso Robles, CA",
    "42100": "Santa Cruz-Watsonville, CA",
    "42140": "Santa Fe, NM",
    "42200": "Santa Maria-Santa Barbara, CA",
    "42220": "Santa Rosa-Petaluma, CA",
    "42340": "Savannah, GA",
    "42540": "Scranton--Wilkes-Barre, PA",
    "42660": "Seattle-Tacoma-Bellevue, WA",
    "42680": "Sebastian-Vero Beach, FL",
    "42700": "Sebring-Avon Park, FL",
    "43100": "Sheboygan, WI",
    "43300": "Sherman-Denison, TX",
    "43340": "Shreveport-Bossier City, LA",
    "43420": "Sierra Vista-Douglas, AZ",
    "43580": "Sioux City, IA",
    "43620": "Sioux Falls, SD",
    "43780": "South Bend-Mishawaka, IN",
    "43900": "Spartanburg, SC",
    "44060": "Spokane-Spokane Valley, WA",
    "44100": "Springfield, IL",
    "44140": "Springfield, MA",
    "44180": "Springfield, MO",
    "44220": "Springfield, OH",
    "44300": "State College, PA",
    "44420": "Staunton, VA",
    "44700": "Stockton, CA",
    "44940": "Sumter, SC",
    "45060": "Syracuse, NY",
    "45220": "Tallahassee, FL",
    "45300": "Tampa-St. Petersburg-Clearwater, FL",
    "45460": "Terre Haute, IN",
    "45500": "Texarkana, TX",
    "45540": "The Villages, FL",
    "45780": "Toledo, OH",
    "45820": "Topeka, KS",
    "45940": "Trenton-Princeton, NJ",
    "46060": "Tucson, AZ",
    "46140": "Tulsa, OK",
    "46220": "Tuscaloosa, AL",
    "46300": "Twin Falls, ID",
    "46340": "Tyler, TX",
    "46520": "Urban Honolulu, HI",
    "46540": "Utica-Rome, NY",
    "46660": "Valdosta, GA",
    "46700": "Vallejo, CA",
    "47020": "Victoria, TX",
    "47220": "Vineland-Bridgeton, NJ",
    "47260": "Virginia Beach-Norfolk-Newport News, VA",
    "47300": "Visalia, CA",
    "47380": "Waco, TX",
    "47460": "Walla Walla, WA",
    "47580": "Warner Robins, GA",
    "47900": "Washington-Arlington-Alexandria, DC",
    "47940": "Waterloo-Cedar Falls, IA",
    "48060": "Watertown-Fort Drum, NY",
    "48140": "Wausau-Weston, WI",
    "48260": "Weirton-Steubenville, WV",
    "48300": "Wenatchee, WA",
    "48540": "Wheeling, WV",
    "48620": "Wichita, KS",
    "48660": "Wichita Falls, TX",
    "48700": "Williamsport, PA",
    "48900": "Wilmington, NC",
    "49020": "Winchester, VA",
    "49180": "Winston-Salem, NC",
    "49340": "Worcester, MA",
    "49420": "Yakima, WA",
    "49620": "York-Hanover, PA",
    "49660": "Youngstown-Warren-Boardman, OH",
    "49700": "Yuba City, CA",
    "49740": "Yuma, AZ",
}

COUNTIES = {
    # New York
    "36061": "New York County (Manhattan), NY",
    "36047": "Kings County (Brooklyn), NY",
    "36081": "Queens County, NY",
    "36005": "Bronx County, NY",
    "36085": "Richmond County (Staten Island), NY",
    "36059": "Nassau County, NY",
    "36103": "Suffolk County, NY",
    "36119": "Westchester County, NY",
    # California
    "06075": "San Francisco County, CA",
    "06037": "Los Angeles County, CA",
    "06073": "San Diego County, CA",
    "06085": "Santa Clara County, CA",
    "06001": "Alameda County, CA",
    "06013": "Contra Costa County, CA",
    "06081": "San Mateo County, CA",
    "06059": "Orange County, CA",
    "06065": "Riverside County, CA",
    "06071": "San Bernardino County, CA",
    "06067": "Sacramento County, CA",
    "06041": "Marin County, CA",
    "06097": "Sonoma County, CA",
    "06055": "Napa County, CA",
    # Texas
    "48201": "Harris County (Houston), TX",
    "48113": "Dallas County, TX",
    "48029": "Bexar County (San Antonio), TX",
    "48439": "Tarrant County (Fort Worth), TX",
    "48453": "Travis County (Austin), TX",
    "48491": "Williamson County, TX",
    # Florida
    "12086": "Miami-Dade County, FL",
    "12011": "Broward County (Fort Lauderdale), FL",
    "12099": "Palm Beach County, FL",
    "12095": "Orange County (Orlando), FL",
    "12057": "Hillsborough County (Tampa), FL",
    "12103": "Pinellas County (St. Petersburg), FL",
    "12031": "Duval County (Jacksonville), FL",
    # Illinois
    "17031": "Cook County (Chicago), IL",
    "17043": "DuPage County, IL",
    "17097": "Lake County, IL",
    # Pennsylvania
    "42101": "Philadelphia County, PA",
    "42003": "Allegheny County (Pittsburgh), PA",
    "42091": "Montgomery County, PA",
    # Massachusetts
    "25025": "Suffolk County (Boston), MA",
    "25017": "Middlesex County, MA",
    "25009": "Essex County, MA",
    # Georgia
    "13121": "Fulton County (Atlanta), GA",
    "13089": "DeKalb County, GA",
    "13067": "Cobb County, GA",
    # Washington
    "53033": "King County (Seattle), WA",
    "53053": "Pierce County (Tacoma), WA",
    "53061": "Snohomish County, WA",
    # Colorado
    "08031": "Denver County, CO",
    "08005": "Arapahoe County, CO",
    "08035": "Douglas County, CO",
    "08059": "Jefferson County, CO",
    # Arizona
    "04013": "Maricopa County (Phoenix), AZ",
    "04019": "Pima County (Tucson), AZ",
    # Michigan
    "26163": "Wayne County (Detroit), MI",
    "26125": "Oakland County, MI",
    "26099": "Macomb County, MI",
    # Ohio
    "39035": "Cuyahoga County (Cleveland), OH",
    "39049": "Franklin County (Columbus), OH",
    "39061": "Hamilton County (Cincinnati), OH",
    # North Carolina
    "37183": "Wake County (Raleigh), NC",
    "37119": "Mecklenburg County (Charlotte), NC",
    "37063": "Durham County, NC",
    # Virginia
    "51059": "Fairfax County, VA",
    "51013": "Arlington County, VA",
    "51107": "Loudoun County, VA",
    "51810": "Virginia Beach (city), VA",
    # Maryland
    "24031": "Montgomery County, MD",
    "24005": "Baltimore County, MD",
    "24003": "Anne Arundel County, MD",
    "24033": "Prince George's County, MD",
    # New Jersey
    "34013": "Essex County (Newark), NJ",
    "34023": "Middlesex County, NJ",
    "34003": "Bergen County, NJ",
    "34017": "Hudson County (Jersey City), NJ",
    # Oregon
    "41051": "Multnomah County (Portland), OR",
    "41005": "Clackamas County, OR",
    "41067": "Washington County, OR",
    # Minnesota
    "27053": "Hennepin County (Minneapolis), MN",
    "27123": "Ramsey County (St. Paul), MN",
    # Missouri
    "29510": "St. Louis (city), MO",
    "29189": "St. Louis County, MO",
    "29095": "Jackson County (Kansas City), MO",
    # Tennessee
    "47037": "Davidson County (Nashville), TN",
    "47157": "Shelby County (Memphis), TN",
    # Connecticut
    "09001": "Fairfield County, CT",
    "09003": "Hartford County, CT",
    "09009": "New Haven County, CT",
    # Indiana
    "18097": "Marion County (Indianapolis), IN",
    # Wisconsin
    "55079": "Milwaukee County, WI",
    "55025": "Dane County (Madison), WI",
    # Nevada
    "32003": "Clark County (Las Vegas), NV",
    # Louisiana
    "22071": "Orleans Parish (New Orleans), LA",
    # Hawaii
    "15003": "Honolulu County, HI",
    # District of Columbia
    "11001": "District of Columbia",
}

STATES = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
    "06": "California", "08": "Colorado", "09": "Connecticut",
    "10": "Delaware", "11": "District of Columbia", "12": "Florida",
    "13": "Georgia", "15": "Hawaii", "16": "Idaho", "17": "Illinois",
    "18": "Indiana", "19": "Iowa", "20": "Kansas", "21": "Kentucky",
    "22": "Louisiana", "23": "Maine", "24": "Maryland", "25": "Massachusetts",
    "26": "Michigan", "27": "Minnesota", "28": "Mississippi", "29": "Missouri",
    "30": "Montana", "31": "Nebraska", "32": "Nevada", "33": "New Hampshire",
    "34": "New Jersey", "35": "New Mexico", "36": "New York",
    "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
    "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania",
    "44": "Rhode Island", "45": "South Carolina", "46": "South Dakota",
    "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont",
    "51": "Virginia", "53": "Washington", "54": "West Virginia",
    "55": "Wisconsin", "56": "Wyoming",
}

# Family configuration labels: key -> (display name, column index in tables)
FAMILY_KEYS = [
    "1a0c", "1a1c", "1a2c", "1a3c",
    "2a1w0c", "2a1w1c", "2a1w2c", "2a1w3c",
    "2a2w0c", "2a2w1c", "2a2w2c", "2a2w3c",
]

FAMILY_LABELS = {
    "1a0c": "1 Adult, 0 Children",
    "1a1c": "1 Adult, 1 Child",
    "1a2c": "1 Adult, 2 Children",
    "1a3c": "1 Adult, 3 Children",
    "2a1w0c": "2 Adults (1 Working), 0 Children",
    "2a1w1c": "2 Adults (1 Working), 1 Child",
    "2a1w2c": "2 Adults (1 Working), 2 Children",
    "2a1w3c": "2 Adults (1 Working), 3 Children",
    "2a2w0c": "2 Adults (Both Working), 0 Children",
    "2a2w1c": "2 Adults (Both Working), 1 Child",
    "2a2w2c": "2 Adults (Both Working), 2 Children",
    "2a2w3c": "2 Adults (Both Working), 3 Children",
}

EXPENSE_CATEGORIES = [
    "Food",
    "Child Care",
    "Medical",
    "Housing",
    "Transportation",
    "Civic",
    "Internet & Mobile",
    "Other",
]

# The full list of row labels we look for in the annual expenses table,
# including required income rows.
ANNUAL_ROW_LABELS = EXPENSE_CATEGORIES + [
    "Required annual income before taxes",
    "Annual taxes",
    "Required annual income after taxes",
]


# ---------------------------------------------------------------------------
# Search / lookup helpers
# ---------------------------------------------------------------------------

def search_locations(query: str) -> list[tuple[str, str, str]]:
    """Fuzzy-search metros, counties, and states. Returns list of (type, code, name)."""
    q = query.lower()
    results: list[tuple[str, str, str]] = []

    for code, name in METROS.items():
        if q in name.lower():
            results.append(("metro", code, name))
    for code, name in COUNTIES.items():
        if q in name.lower():
            results.append(("county", code, name))
    for code, name in STATES.items():
        if q in name.lower():
            results.append(("state", code, name))

    return results


def resolve_search_term(term: str) -> tuple[str, str, str]:
    """Resolve a search term to (type, code, name). Exits on ambiguity."""
    matches = search_locations(term)
    if not matches:
        print(f"Error: No location found matching '{term}'.")
        print("Use --list to see available locations, or provide codes directly.")
        sys.exit(1)
    if len(matches) == 1:
        return matches[0]

    # Check which location types matched
    types_found = set(m[0] for m in matches)

    # If only one type matched, apply within-type disambiguation
    if len(types_found) == 1:
        typ = types_found.pop()
        # For a single type with one result, return it
        if len(matches) == 1:
            return matches[0]
        # Prefer match whose name starts with the query
        starting = [m for m in matches if m[2].lower().startswith(term.lower())]
        if len(starting) == 1:
            return starting[0]

    # Multiple types matched — if only one metro, prefer it (most common use case)
    metro_matches = [m for m in matches if m[0] == "metro"]
    county_matches = [m for m in matches if m[0] == "county"]
    state_matches = [m for m in matches if m[0] == "state"]

    # If there are both metros and counties (and/or states), always disambiguate
    # so the user can pick the right granularity
    if metro_matches and county_matches:
        _print_disambiguation(term, matches)
        sys.exit(1)

    # Only metros matched (multiple) — try narrowing
    if metro_matches and not county_matches:
        if len(metro_matches) == 1:
            return metro_matches[0]
        starting = [m for m in metro_matches if m[2].lower().startswith(term.lower())]
        if len(starting) == 1:
            return starting[0]

    # Only counties matched (multiple) — try narrowing
    if county_matches and not metro_matches:
        if len(county_matches) == 1:
            return county_matches[0]
        starting = [m for m in county_matches if m[2].lower().startswith(term.lower())]
        if len(starting) == 1:
            return starting[0]

    # If no metro or county match, prefer exact state name match
    if not metro_matches and not county_matches:
        for m in state_matches:
            if m[2].lower() == term.lower():
                return m

    _print_disambiguation(term, matches)
    sys.exit(1)


def _print_disambiguation(term: str, matches: list[tuple[str, str, str]]) -> None:
    """Print disambiguation list grouped by type."""
    type_order = ["metro", "county", "state"]
    type_labels = {"metro": "Metro Areas", "county": "Counties", "state": "States"}
    type_flags = {"metro": "--metros", "county": "--counties", "state": "--states"}

    print(f"Multiple locations match '{term}':")
    for typ in type_order:
        group = [m for m in matches if m[0] == typ]
        if group:
            print(f"\n  {type_labels[typ]}:")
            flag = type_flags[typ]
            for _, code, name in group:
                print(f"    {flag} {code}  {name}")
    print(f"\nTip: use --metros, --counties, or --states with the codes above.")


def location_url(loc_type: str, code: str) -> str:
    """Build MIT Living Wage Calculator URL."""
    base = "https://livingwage.mit.edu"
    if loc_type == "metro":
        return f"{base}/metros/{code}"
    elif loc_type == "county":
        return f"{base}/counties/{code}"
    elif loc_type == "state":
        return f"{base}/states/{code}"
    else:
        print(f"Error: Unknown location type '{loc_type}'.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Scraping / parsing
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> BeautifulSoup:
    """Fetch a page and return parsed HTML."""
    headers = {
        "User-Agent": (
            "COL-Compare-Tool/1.0 (cost-of-living research; "
            "respects 10-location fair-use policy)"
        ),
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def parse_dollar(text: str) -> Optional[float]:
    """Parse a dollar string like '$1,234' or '$1,234.56' to float."""
    text = text.strip().replace(",", "").replace("$", "").replace("−", "-").replace("–", "-")
    if not text or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_wage(text: str) -> Optional[float]:
    """Parse a wage string like '$28.89' to float."""
    return parse_dollar(text)


def _extract_table_rows(soup: BeautifulSoup, table_id: str) -> list[list[str]]:
    """Extract rows from a table by its id. Returns list of [label, val1, val2, ...]."""
    table = soup.find("table", id=table_id)
    if not table:
        return []
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if cells:
            rows.append([c.get_text(strip=True) for c in cells])
    return rows


def _find_table_by_heading(soup: BeautifulSoup, heading_text: str) -> Optional[BeautifulSoup]:
    """Find a table that follows a heading containing the given text."""
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "div"]):
        if heading_text.lower() in heading.get_text(strip=True).lower():
            table = heading.find_next("table")
            if table:
                return table
    return None


def _parse_table_to_rows(table) -> list[list[str]]:
    """Parse a BeautifulSoup table element into a list of text rows."""
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if cells:
            rows.append([c.get_text(strip=True) for c in cells])
    return rows


def _match_row_label(row_label: str, target: str) -> bool:
    """Check if a row label matches a target category, with fuzzy matching."""
    rl = row_label.lower().strip()
    tl = target.lower().strip()
    # Direct containment
    if tl in rl or rl in tl:
        return True
    # Handle some known variations
    aliases = {
        "internet & mobile": ["broadband", "internet", "telephone"],
        "civic": ["civic"],
        "other": ["other necessities", "other"],
        "food": ["food"],
        "child care": ["child care", "childcare"],
        "medical": ["medical"],
        "housing": ["housing"],
        "transportation": ["transportation"],
        "required annual income before taxes": [
            "required annual income before taxes",
            "annual income before taxes",
            "income before taxes",
        ],
        "annual taxes": ["annual taxes", "taxes"],
        "required annual income after taxes": [
            "required annual income after taxes",
            "annual income after taxes",
            "income after taxes",
        ],
    }
    for key, als in aliases.items():
        if tl == key:
            return any(a in rl for a in als)
    return False


def parse_location_data(soup: BeautifulSoup) -> dict:
    """Parse all relevant data from a Living Wage Calculator page.

    Returns dict with:
        name: str - location name
        wages: dict[family_key -> float] - hourly living wage
        expenses: dict[category -> dict[family_key -> float]] - annual expenses
        income_before_tax: dict[family_key -> float]
        income_after_tax: dict[family_key -> float]
        taxes: dict[family_key -> float]
    """
    data: dict = {}

    # Extract location name from heading or title
    # The h1 is the site logo; the location is in an h2 like
    # "Living Wage Calculation for Atlanta-Sandy Springs-Alpharetta, GA"
    name = "Unknown"
    for heading in soup.find_all(["h2", "h3"]):
        text = heading.get_text(strip=True)
        for prefix in [
            "Living Wage Calculation for ",
            "Living Wage Calculator for ",
        ]:
            if text.startswith(prefix):
                name = text[len(prefix):]
                break
        if name != "Unknown":
            break

    if name == "Unknown":
        title = soup.find("title")
        if title:
            t = title.get_text(strip=True)
            m = re.search(r"for\s+(.+)$", t)
            if m:
                name = m.group(1).strip()

    data["name"] = name

    # --- Parse hourly living wage table ---
    # Look for table with "Living Wage" as header
    wage_table = None
    for table in soup.find_all("table"):
        text = table.get_text(strip=True).lower()
        if "living wage" in text and ("poverty wage" in text or "minimum wage" in text):
            wage_table = table
            break

    wages = {}
    if wage_table:
        rows = _parse_table_to_rows(wage_table)
        for row in rows:
            if row and "living wage" in row[0].lower():
                values = row[1:]  # skip label
                for i, key in enumerate(FAMILY_KEYS):
                    if i < len(values):
                        w = parse_wage(values[i])
                        if w is not None:
                            wages[key] = w
                break
    data["wages"] = wages

    # --- Parse annual expenses table ---
    # Look for the "Typical Expenses" table
    expense_table = None
    for table in soup.find_all("table"):
        table_text = table.get_text(strip=True).lower()
        if "typical expenses" in table_text or (
            "food" in table_text and "housing" in table_text and "transportation" in table_text
        ):
            # Check it has dollar amounts (to distinguish from the wage table)
            first_data_row = None
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if cells and len(cells) > 1:
                    first_data_row = cells
                    break
            if first_data_row and "$" in first_data_row[0].get_text():
                # This is likely the right table, but the label is in the first column
                pass
            if first_data_row:
                expense_table = table
                break

    expenses: dict[str, dict[str, float]] = {}
    income_before_tax: dict[str, float] = {}
    income_after_tax: dict[str, float] = {}
    taxes: dict[str, float] = {}

    if expense_table:
        rows = _parse_table_to_rows(expense_table)
        for row in rows:
            if not row or len(row) < 2:
                continue
            label = row[0]
            values = row[1:]

            # Check each known category
            for cat in EXPENSE_CATEGORIES:
                if _match_row_label(label, cat):
                    expenses[cat] = {}
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                expenses[cat][key] = v
                    break
            else:
                # Check income/tax rows
                if _match_row_label(label, "Required annual income before taxes"):
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                income_before_tax[key] = v
                elif _match_row_label(label, "Annual taxes"):
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                taxes[key] = v
                elif _match_row_label(label, "Required annual income after taxes"):
                    for i, key in enumerate(FAMILY_KEYS):
                        if i < len(values):
                            v = parse_dollar(values[i])
                            if v is not None:
                                income_after_tax[key] = v

    data["expenses"] = expenses
    data["income_before_tax"] = income_before_tax
    data["income_after_tax"] = income_after_tax
    data["taxes"] = taxes

    return data


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def compute_equivalent_income(
    income_a: float, lw_before_tax_a: float, lw_before_tax_b: float
) -> float:
    """Compute equivalent income in location B for someone earning income_a in A.

    Uses blended approach:
    - Living wage portion scales by full COL ratio
    - Excess income scales by sqrt of COL ratio (dampened)
    """
    if lw_before_tax_a <= 0 or lw_before_tax_b <= 0:
        return income_a

    ratio = lw_before_tax_b / lw_before_tax_a

    if income_a <= lw_before_tax_a:
        return income_a * ratio
    else:
        base = lw_before_tax_b
        excess = (income_a - lw_before_tax_a) * math.sqrt(ratio)
        return base + excess


def format_dollar(val: float) -> str:
    """Format a float as a dollar string."""
    if val < 0:
        return f"-${abs(val):,.0f}"
    return f"${val:,.0f}"


def format_pct(val: float) -> str:
    """Format a percentage change."""
    if val > 0:
        return f"+{val:.1f}%"
    return f"{val:.1f}%"


def pct_diff(a: float, b: float) -> Optional[float]:
    """Percentage difference of b relative to a."""
    if a == 0:
        return None
    return ((b - a) / a) * 100


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_comparison(
    locations: list[dict],
    family: str,
    income: Optional[float] = None,
) -> None:
    """Print a formatted comparison table."""
    family_label = FAMILY_LABELS.get(family, family)
    names = [loc["name"] for loc in locations]

    print()
    print("Cost of Living Comparison")
    print("=" * 60)
    print("  vs  ".join(names))
    print(f"Family type: {family_label}")
    print()

    # --- Headline income equivalence ---
    if income is not None and len(locations) >= 2:
        ref = locations[0]
        ref_bt = ref["income_before_tax"].get(family)
        if ref_bt:
            print("INCOME EQUIVALENCE")
            print("-" * 60)
            for loc in locations[1:]:
                loc_bt = loc["income_before_tax"].get(family)
                if loc_bt:
                    equiv = compute_equivalent_income(income, ref_bt, loc_bt)
                    diff_pct = pct_diff(income, equiv)
                    direction = "less" if diff_pct and diff_pct < 0 else "more"
                    pct_str = f" ({abs(diff_pct):.1f}% {direction})" if diff_pct else ""
                    print(
                        f"  {format_dollar(income)} in {ref['name']}"
                        f"  ~  {format_dollar(equiv)} in {loc['name']}{pct_str}"
                    )
            print()

    # --- Expense breakdown ---
    # Column widths
    cat_width = 20
    val_width = max(14, max(len(n) for n in names) + 2)

    # Header
    header = f"{'Category':<{cat_width}}"
    for name in names:
        header += f"{name:>{val_width}}"
    if len(locations) >= 2:
        header += f"{'Diff':>10}"
    print("Expense Breakdown (Annual):")
    print(header)
    print("\u2500" * len(header))

    total_by_loc: list[float] = [0.0] * len(locations)

    for cat in EXPENSE_CATEGORIES:
        row = f"{cat:<{cat_width}}"
        vals: list[Optional[float]] = []
        for loc in locations:
            v = loc["expenses"].get(cat, {}).get(family)
            vals.append(v)
        for i, v in enumerate(vals):
            if v is not None:
                row += f"{format_dollar(v):>{val_width}}"
                total_by_loc[i] += v
            else:
                row += f"{'N/A':>{val_width}}"
        if len(locations) >= 2 and vals[0] is not None and vals[1] is not None:
            pd = pct_diff(vals[0], vals[1])
            row += f"{format_pct(pd) if pd is not None else 'N/A':>10}"
        print(row)

    # Taxes row
    row = f"{'Taxes':<{cat_width}}"
    tax_vals: list[Optional[float]] = []
    for loc in locations:
        v = loc["taxes"].get(family)
        tax_vals.append(v)
    for i, v in enumerate(tax_vals):
        if v is not None:
            row += f"{format_dollar(v):>{val_width}}"
            total_by_loc[i] += v
        else:
            row += f"{'N/A':>{val_width}}"
    if len(locations) >= 2 and tax_vals[0] is not None and tax_vals[1] is not None:
        pd = pct_diff(tax_vals[0], tax_vals[1])
        row += f"{format_pct(pd) if pd is not None else 'N/A':>10}"
    print(row)

    print("\u2500" * len(header))

    # Total before tax row
    row = f"{'Total (pre-tax)':<{cat_width}}"
    bt_vals: list[Optional[float]] = []
    for loc in locations:
        v = loc["income_before_tax"].get(family)
        bt_vals.append(v)
    for i, v in enumerate(bt_vals):
        if v is not None:
            row += f"{format_dollar(v):>{val_width}}"
        else:
            row += f"{'N/A':>{val_width}}"
    if len(locations) >= 2 and bt_vals[0] is not None and bt_vals[1] is not None:
        pd = pct_diff(bt_vals[0], bt_vals[1])
        row += f"{format_pct(pd) if pd is not None else 'N/A':>10}"
    print(row)

    print()

    # Living wage
    row = f"{'Living Wage':<{cat_width}}"
    for loc in locations:
        w = loc["wages"].get(family)
        if w is not None:
            row += f"{'${:.2f}/hr'.format(w):>{val_width}}"
        else:
            row += f"{'N/A':>{val_width}}"
    print(row)

    print()
    print("Data source: MIT Living Wage Calculator (https://livingwage.mit.edu)")
    print()


def print_single_location(loc: dict, family: str) -> None:
    """Print data for a single location."""
    family_label = FAMILY_LABELS.get(family, family)
    print()
    print(f"Living Wage Data: {loc['name']}")
    print("=" * 50)
    print(f"Family type: {family_label}")
    print()

    wage = loc["wages"].get(family)
    if wage is not None:
        print(f"  Living Wage: ${wage:.2f}/hr")

    bt = loc["income_before_tax"].get(family)
    if bt is not None:
        print(f"  Required Annual Income (before tax): {format_dollar(bt)}")

    at = loc["income_after_tax"].get(family)
    if at is not None:
        print(f"  Required Annual Income (after tax):  {format_dollar(at)}")

    print()
    print("  Annual Expenses:")
    for cat in EXPENSE_CATEGORIES:
        v = loc["expenses"].get(cat, {}).get(family)
        if v is not None:
            print(f"    {cat:<22} {format_dollar(v)}")

    tax = loc["taxes"].get(family)
    if tax is not None:
        print(f"    {'Taxes':<22} {format_dollar(tax)}")

    print()
    print("Data source: MIT Living Wage Calculator (https://livingwage.mit.edu)")
    print()


def list_locations() -> None:
    """Print all known locations."""
    print("\nMetro Areas (use with --metros <code>):")
    print("-" * 60)
    for code, name in sorted(METROS.items(), key=lambda x: x[1]):
        print(f"  {code}  {name}")

    print(f"\nCounties (use with --counties <code>):")
    print("-" * 60)
    for code, name in sorted(COUNTIES.items(), key=lambda x: x[1]):
        print(f"  {code}  {name}")

    print(f"\nStates (use with --states <code>):")
    print("-" * 60)
    for code, name in sorted(STATES.items(), key=lambda x: x[1]):
        print(f"  {code}  {name}")
    print()
    print("Any county or metro can also be used by FIPS/CBSA code directly,")
    print("even if not listed above. Find codes at https://livingwage.mit.edu")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare cost of living between US locations using MIT Living Wage data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --search "New York" "Atlanta"
  %(prog)s --search "New York" "Atlanta" --income 120000
  %(prog)s --search "San Francisco" "Austin" --family 2a2w1c
  %(prog)s --metros 35620 12060
  %(prog)s --counties 06075 06037
  %(prog)s --states 06 48
  %(prog)s --list
        """,
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--search", nargs="+", metavar="TERM",
        help="Search for locations by name (e.g., 'New York' 'Atlanta')",
    )
    group.add_argument(
        "--metros", nargs="+", metavar="CBSA",
        help="Metro areas by CBSA code (e.g., 35620 12060)",
    )
    group.add_argument(
        "--counties", nargs="+", metavar="FIPS",
        help="Counties by FIPS code (e.g., 06075 06037)",
    )
    group.add_argument(
        "--states", nargs="+", metavar="FIPS",
        help="States by FIPS code (e.g., 06 48)",
    )
    group.add_argument(
        "--list", action="store_true",
        help="List all known metro areas and states",
    )

    parser.add_argument(
        "--family", default="1a0c",
        choices=FAMILY_KEYS,
        help="Family configuration (default: 1a0c = 1 Adult, 0 Children)",
    )
    parser.add_argument(
        "--income", type=float, default=None,
        help="Annual income in first location for equivalence calculation",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        list_locations()
        return

    # Resolve locations
    loc_specs: list[tuple[str, str]] = []  # (type, code)

    if args.search:
        for term in args.search:
            typ, code, name = resolve_search_term(term)
            loc_specs.append((typ, code))
    elif args.metros:
        for code in args.metros:
            loc_specs.append(("metro", code))
    elif args.counties:
        for code in args.counties:
            loc_specs.append(("county", code))
    elif args.states:
        for code in args.states:
            loc_specs.append(("state", code))
    else:
        parser.print_help()
        return

    if not loc_specs:
        print("Error: No locations specified.")
        sys.exit(1)

    # Fetch data for each location
    location_data: list[dict] = []
    for loc_type, code in loc_specs:
        url = location_url(loc_type, code)
        print(f"Fetching data from {url} ...", file=sys.stderr)
        try:
            soup = fetch_page(url)
            data = parse_location_data(soup)
            data["url"] = url
            location_data.append(data)
        except requests.HTTPError as e:
            print(f"Error fetching {url}: {e}", file=sys.stderr)
            sys.exit(1)
        except requests.ConnectionError as e:
            print(f"Connection error for {url}: {e}", file=sys.stderr)
            sys.exit(1)

    # Display
    family = args.family
    if len(location_data) == 1:
        print_single_location(location_data[0], family)
    else:
        print_comparison(location_data, family, income=args.income)


if __name__ == "__main__":
    main()
