# yahoo_fantasy_football_data
Connect to the Yahoo API, pull down data on your fantasy football league (past and present years), and generate master dataset for analysis

# Purpose
There's still a long way to go, but the primary objective is to make your fantasy football league's data more accessible for insights. Have fun and don't get too discouraged when you find out how much of the game can be random.

# Getting started
I know right now there isn't much detail on how to get started. I'll add that soon, I hope. For now, get started by creating an app here: 
https://developer.yahoo.com/apps/create/

# How to use this code
https://github.com/calebfleming/yahoo_fantasy_football_data/blob/master/example_usage.ipynb

After I get the full set of data, be it for 1 year or 3, I either do my analysis in Python or Tableau (via csv export). That part is up to you though -- I'm just here to get you access to all the data that Yahoo makes available via their API.

This includes:
- Rosters by week
- Player stats by week
- Team performance by week (scoreboard)
- Standings for the most recent week (either the end of a completed season or the current week in an active season)
- Draft results

There's also a separate function within the cleanse class to get the points per week by draft pick number. This was a special request for one of my league members -- feel free to ignore if it's of no interest to you. I hope to add more functionality like this though, preferably broken into separate modules from the main classes that pull and clean.

# Known bugs (by me at least)
It seems that the NFL team associated with a given player is always their current team, not the team for the respective week and year. I don't think this is a bug in my code, but maybe it is :shrug:

Feel free to add more and reach out with questions
