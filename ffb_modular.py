###resources that helped me a lot
#https://github.com/josuebrunel/yahoo-oauth/blob/master/README.md
#https://developer.yahoo.com/apps/WCeIk444/

import xmltodict
import time
import os
from collections import OrderedDict
import unicodecsv
from yahoo_oauth import OAuth2
import pandas as pd
import numpy as np
import yaml

"""To add:
- Instrucitons on how to get your creds and leagues
- Sample insights
- Make authentication flow easier (less redundant)
- Figure out rate limiting solution (if you want to pull the last 5 years, for example)
- More cleanup -- NULLs, for example
"""


class get_results:
  def __init__(self, year = 2019, maxweek = 1):
    # get creds
    with open("yahoo_creds.yaml", 'r') as yahoo_creds:
      creds = yaml.safe_load(yahoo_creds)

    with open("yahoo_leagues.yaml", 'r') as yahoo_leagues:
      leagues = yaml.safe_load(yahoo_leagues)

    self.oauth = OAuth2(creds['key'], creds['secret'])
    self.guid = self.oauth.guid
    self.leagues = leagues['leagues']
    self.year = year
    self.week = maxweek+1

    #parse uniqueId
    output = [(l['gameid'],l['leagueid']) for l in self.leagues if l['year'] == self.year]
    self.uniqueId = f'{output[0][0]}.l.{output[0][1]}'
  
  def __run_query(self, query):
    y_session = self.oauth
    r = y_session.session.get(query)
    if (r.status_code >= 500):
        print('Bad response from yahoo: status code {0}.  retrying...'.format(r.status_code))
        r = y_session.session.get(query)
    return xmltodict.parse(r.content)

  def get_teams(self):
    z = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.uniqueId}/teams")
    teams = [{'team_key':i['team_key'], 'team_name':i['name']} for i in z['fantasy_content']['league']['teams']['team']]
    return teams
  
  def get_standings(self):
    z = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.uniqueId}/standings")    
    standings = [{'name':i['name']
                  , 'owner': i['managers']['manager']['nickname']
                  , 'teamKey' : i['team_key']
                  , 'trades': i['number_of_trades']
                  , 'moves': i['number_of_moves']
                  , 'draftGrade' : i['draft_grade']
                  , 'points_for' : i['team_standings']['points_for']
                  , 'points_against' : i['team_standings']['points_against']
                  , 'percentage' : i['team_standings']['outcome_totals']['percentage']
                  , 'rank' : i['team_standings']['rank']
                  , 'playoff_seed' : i['team_standings']['playoff_seed']
                 }
                 for i in z['fantasy_content']['league']['standings']['teams']['team']]
    return standings

  def get_scores(self):
    scoreboard = []
    for w in range(1,self.week):
      try:
        z = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.uniqueId}/scoreboard;week={w}")
        scores = [{'week': w
                  , 'is_playoffs': i['is_playoffs']
                  , 'is_consolation': i['is_consolation']
                  , 'is_tied': i['is_tied']
                  , 'winner_key': i['winner_team_key']
                  , 'team_1_key': i['teams']['team'][0]['team_key']
                  , 'team_1_name' : i['teams']['team'][0]['name']
                  , 'team_1_proj' : i['teams']['team'][0]['team_projected_points']['total']
                  , 'team_1_act' : i['teams']['team'][0]['team_points']['total']
                  , 'team_2_proj' : i['teams']['team'][1]['team_projected_points']['total']
                  , 'team_2_act' :  i['teams']['team'][1]['team_points']['total']
                  , 'team_2_key' : i['teams']['team'][1]['team_key']
                  , 'team_2_name' : i['teams']['team'][1]['name']
                }
                for i in z['fantasy_content']['league']['scoreboard']['matchups']['matchup']]
        scoreboard.append(scores)
      except:
          return [item for sublist in scoreboard for item in sublist]
      
    return [item for sublist in scoreboard for item in sublist]

  def __roster_prep(self, teamId):
    rosters = []
    for w in range(1,self.week):
      z = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/team/{teamId}/roster;week={w}")
      r = [{'week': w
              , 'manager': z['fantasy_content']['team']['name']
              , 'manager_key': z['fantasy_content']['team']['team_key']
              , 'player_name':i['name']['full']
              , 'player_key' : i['player_key']
              , 'team_name':i['editorial_team_full_name']
              , 'pos':i['selected_position']['position']
              , 'bye_week': str(w) == i['bye_weeks']['week']
                }
                for i in z['fantasy_content']['team']['roster']['players']['player']]
      rosters.append(r)
    return [item for sublist in rosters for item in sublist]

  def get_rosters(self, teams = False):
    if not teams:
      teams = self.get_teams()
    if not isinstance(teams, (list, tuple)):
      teams = [{'team_key':teams}]
    rosters = [self.__roster_prep(t['team_key']) for t in teams]
    flat_roster = [item for sublist in rosters for item in sublist]
    return flat_roster

  def __get_all_stats(self, player, statsMeta):
    tmp = pd.DataFrame(player['player_stats']['stats']['stat'])
    tmp['value'] = tmp['value'].astype(float)
    pstats_df = (pd.merge(statsMeta, 
          tmp, 
          how='right', 
          left_on = 'stat_id', 
          right_on = 'stat_id')
         [['name','value']]
                 .set_index('name').T
                 .fillna(0.0)
                )
    pstats_dict = pstats_df.to_dict(orient='records')
    return pstats_dict[0]

  def get_player_stats(self, players):    
    # get league stat lookup
    y = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.uniqueId}/settings")
    statMeta = (pd.DataFrame(y['fantasy_content']['league']['settings']['stat_categories']['stats']['stat'])[['stat_id','name']])
    
    stats = []
    for w in range(1,self.week):
      z = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.uniqueId}/players;player_keys={players}/stats;type=week;week={w}")
      e = z['fantasy_content']['league']['players']['player']
      p = [{'week': w
        , 'player_key': i['player_key']
        #, 'team_name': i['editorial_team_full_name']
        , 'player_name': i['name']['full']
        , 'points': i['player_points']['total']
        , **self.__get_all_stats(i, statMeta)} for i in e]
      stats.append(p)
    return [item for sublist in stats for item in sublist]  

  #get all players and uniqueId
  def get_players(self, rosters):
    players = list(set([n['player_key'] for n in rosters]))

    # get chunks (I believe the max is 25 per request)
    playerChunks = [players[i:i + 24] for i in range(0, len(players), 24)]

    # iterate over chunks
    output0 = []
    for chunk in playerChunks:  
        p = ",".join([str(x) for x in chunk])
        subset = self.get_player_stats(p)
        output0.append(subset)
        print('chunkDone moving on')
    flatPlayers = [item for sublist in output0 for item in sublist]
    return flatPlayers

  def get_draft(self):
      z = self.__run_query(f"https://fantasysports.yahooapis.com/fantasy/v2/league/{self.uniqueId}/draftresults")
      return z['fantasy_content']['league']['draft_results']['draft_result']

  def full_pull(self):
      # run funcs
      standings = self.get_standings()
      print('standings retrieved')
      
      scores = self.get_scores()
      print('scores retrieved')
      
      teams = self.get_teams()
      print('teams retrieved')
      
      draft_results = self.get_draft()
      print('draft results retrieved')
      
      rosters = self.get_rosters()
      print('rosters retrieved')
      
      players = self.get_players(rosters)
      print('players retrieved')
      
      return standings, scores, teams, rosters, draft_results, players


class get_cleaned:
  def __init__(self, standings, scores, teams, rosters, draft_results, players):
    self.standings = pd.DataFrame(standings)
    self.scores = pd.DataFrame(scores)
    self.teams = pd.DataFrame(teams)
    self.rosters = pd.DataFrame(rosters)
    self.draft_results = pd.DataFrame(draft_results)
    self.players = pd.DataFrame(players).fillna(0.0)

  # merge draft results with player table
  def cleanse_data(self):  
    pOut = pd.merge(self.players, self.draft_results, how='left', left_on='player_key', right_on='player_key')
    pOut['points'] = pOut['points'].astype(float)
    pOut = pd.merge(pOut, self.standings[['teamKey','owner']].drop_duplicates(), how='left', left_on='team_key', right_on='teamKey', copy=False)
    del pOut['team_key']
    del pOut['teamKey']
    pOut = pOut.rename(index = str, columns = {'owner':'draftedBy'})
    
    # merge players with Rosters
    rpOut = pd.merge(self.rosters, pOut, left_on = ['player_key','week'], right_on = ['player_key','week'], how = 'outer')
    rpstJoined = pd.merge(rpOut, self.standings, right_on = 'teamKey', left_on='manager_key', how='outer') 

    # cleanup formatting of points and leagueYear
    rpstJoined['points'] = rpstJoined['points'].astype('float')
    rpstJoined['leagueYear'] = rpstJoined['player_key'].str.split('.p.').apply(lambda x: x[0])
    rpstJoined['leagueYear'] = (rpstJoined['leagueYear']
                              .replace('348','2015')
                              .replace('359','2016')
                              .replace('371','2017')
                              .replace('380','2018')
                              .replace('390','2019')
                              )
    # get number of weeks a player has been owned by an owner                        
    activeWeeks = rpstJoined.groupby(['player_name_x'])['owner'].count().reset_index().rename(columns={'owner':'total_weeks_owned'})
    joined2 = pd.merge(rpstJoined, activeWeeks, left_on = 'player_name_y', right_on = 'player_name_x', how='left')
    joined2 = joined2.rename(columns={'team_name':'player_team_name'})

    # clean up scores table formatting
    self.scores['team_1_act'] = self.scores['team_1_act'].astype(float)
    self.scores['team_2_act'] = self.scores['team_2_act'].astype(float)
    self.scores['team_1_proj'] = self.scores['team_1_proj'].astype(float)
    self.scores['team_2_proj'] = self.scores['team_2_proj'].astype(float)

    self.scores['maxAct'] = self.scores[["team_1_act", "team_2_act"]].max(axis=1)
    self.scores['maxProj'] = self.scores[["team_1_proj", "team_2_proj"]].max(axis=1)

    # cleanup winners and losers
    temp = self.scores.copy()
    temp = temp.reset_index().rename(columns={'index':'game_reference'})

    temp1 = temp[['game_reference','is_consolation','is_playoffs','is_tied','week','team_1_act','team_1_proj','team_1_key','team_1_name','winner_key']]
    temp2 = temp[['game_reference','is_consolation','is_playoffs','is_tied','week','team_2_act','team_2_proj','team_2_key','team_2_name','winner_key']]
    temp1 = temp1.rename(columns={'team_1_act':'actual_points'
                                  , 'team_1_proj':'proj_points'
                                  , 'team_1_key':'team_key'
                                  , 'team_1_name':'team_name'})
    temp2 = temp2.rename(columns={'team_2_act':'actual_points'
                                  , 'team_2_proj':'proj_points'
                                  , 'team_2_key':'team_key'
                                  , 'team_2_name':'team_name'})

    scoreboard2 = pd.concat([temp1,temp2]).sort_values(by='game_reference')
    scoreboard2.week = scoreboard2.week.astype(int)

    # merge back together
    fullSet = pd.merge(joined2, scoreboard2, left_on=['teamKey','week'], right_on=['team_key','week'], how='left')
    fullSet['gameResult'] = np.where(fullSet['team_key']==fullSet['winner_key'], 'W', 'L')

    # get opposing player
    gameRefOwner= fullSet[['game_reference','owner']].drop_duplicates().dropna().sort_values(by='game_reference')
    get_oppo = pd.merge(gameRefOwner, gameRefOwner, on='game_reference', how = 'left', suffixes=['','_opponent'])
    get_oppo = get_oppo[get_oppo['owner']!=get_oppo['owner_opponent']]
    fullSet2 = pd.merge(fullSet, get_oppo, on=['game_reference','owner'], how = 'left')

    # get only the columns we want
    fullSet3 = fullSet2[['bye_week', 'manager', 'pos', 'week', 'player_name_y', 'player_team_name', 'points', 'draftGrade',
       'moves', 'owner', 'percentage', 'playoff_seed',
       'points_against', 'points_for', 'rank', 'trades',
       'leagueYear', 'total_weeks_owned', 'game_reference',
       'is_consolation', 'is_playoffs', 'actual_points', 
       'proj_points', 'owner_opponent', 'gameResult', 'pick','round','draftedBy',
       '2-Point Conversions', 'Block Kick', 'Extra Point Returned',
       'Field Goals 0-19 Yards', 'Field Goals 20-29 Yards',
       'Field Goals 30-39 Yards', 'Field Goals 40-49 Yards',
       'Field Goals 50+ Yards', 'Fumble Recovery', 'Fumbles Lost',
       'Interception', 'Interceptions', 'Kickoff and Punt Return Touchdowns',
       'Offensive Fumble Return TD', 'Passing Touchdowns', 'Passing Yards',
       'Point After Attempt Made', 'Points Allowed', 'Points Allowed 0 points',
       'Points Allowed 1-6 points', 'Points Allowed 14-20 points',
       'Points Allowed 21-27 points', 'Points Allowed 28-34 points',
       'Points Allowed 35+ points', 'Points Allowed 7-13 points',
       'Receiving Touchdowns', 'Receiving Yards', 'Receptions',
       'Return Touchdowns', 'Rushing Attempts', 'Rushing Touchdowns',
       'Rushing Yards', 'Sack', 'Safety', 'Targets', 'Touchdown']]

    #return table
    return fullSet3

  def get_points_by_draft_slot(self):
    df = self.cleanse_data()
    df = df.dropna(subset=['round','pick'])
    df['round'] = df['round'].astype(int)
    df['pick'] = df['pick'].astype(int)
    return df[['round','pick','week','points','player_name_y']].sort_values(by=['round','pick','week'])
  
