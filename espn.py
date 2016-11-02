#!/usr/bin/env python

"""
This is my simple library to scrape NBA and NCB play-by-play information from
ESPN. I needed a small project to test out BeautifulSoup Alpha 4, so I felt
this was a good opportunity to refine some earlier code I had written.

In order to use this, you will need to download bs4 and also lxml (bs4 is
modular and can use both lxml and html5lib as back-end parsers).

The output is in dictionary format and contains the following information for
each individual play: quarter, quarter_time, overall_time, home_score,
away_score, home_play, away_play, and official_play (for timeouts, starts of
quarters, etc). I've found the majority of games normally have around 400 to
460 plays.

"""
from urllib.request import urlopen
import re
import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup as bs
import string

def daterange(start, end):
    """Generator for days between two specific days."""
    for n in range((end - start).days):
        yield start + datetime.timedelta(n)


def _format_scoreboard_url(day, league='nba'):
    """Format ESPN scoreboard link to scrape individual box scores from."""
    league = league.lower()
    link = [league + '/scoreboard/_/date/']
    if isinstance(day, datetime.date):
        link.append(day.strftime('%Y%m%d'))
    else:
        link.append(day)
    if league == 'ncb':
        link.append('&confId=50')
    scoreboard_link = ''.join(['http://www.espn.com/', ''.join(link)])
    return scoreboard_link


def scrape_links(espn_scoreboard):
    """Scrape ESPN's scoreboard for Play-By-Play links."""
    url = urlopen(espn_scoreboard).read().decode('utf-8')
    f2 = url.split(',')
    url_list=[]
    for i in range( len( f2 ) ):
        if ("/nba/recap?gameId=" in f2[i]):
            url_list += [f2[i][-10:-1]]
    return url_list


def adjust_game(plays, league='nba'):
    """
    Takes plays from parse_plays (generator of lists) and the league which
    it is parsing (used for correct quarter/halve time). It returns a list
    of plays in dictionary format -- which is more convenient for lookups.

    The dictionary contains the following information: quarter, quarter_time,
    overall_time, home_score, away_score, home_play, away_play, and 
    official_play (for timeouts, starts of quarters, etc).
    """
    # TODO: Maybe 'period' instead of 'quarter'? NCB uses 'halves'.
    game = []
    quarter = 1
    end_of_quarter = False
    for play in plays:
        try:
            time = play.find('td', {'class': 'time-stamp'}).text
        except:
            continue
        new_play = _play_as_dict(play)
        time_dict, quarter, end_of_quarter = _adjust_time(time,
                quarter, end_of_quarter, league)
        new_play.update(time_dict)
        if(play.find('td', {'class': 'combined-score no-change'})):
            if len(game) > 0:
                # Official Play without score (new quarter, etc.)
                last_play = game[-1]
                new_play['away_score'] = last_play['away_score']
                new_play['home_score'] = last_play['home_score']
            else:
                # Start of game
                new_play['away_score'] = 0
                new_play['home_score'] = 0
        else:
            scores = play.find('td', {'class': 'combined-score '}).text
            away_score, home_score = scores.split('-')
            new_play['away_score'] = int(away_score)
            new_play['home_score'] = int(home_score)
        game.append(new_play)
    return game


def _adjust_time(time, quarter, end_of_quarter, league):
    """
    Takes the time logic out of adjust_game.
    Returns a dict, quarter, and end_of_quarter.
    """
    new_time = re.split(':', time)
    minutes = int(new_time[0])
    seconds = int(new_time[1])
    if minutes == 0 and not end_of_quarter:
        end_of_quarter = True
    elif end_of_quarter and minutes > 1:
        quarter += 1
        end_of_quarter = False
    overall_time = _calc_overall_time(seconds, minutes, quarter, league)
    time_dict = {}
    time_dict['overall_time'] = overall_time
    time_dict['quarter_time'] = time
    time_dict['quarter'] = quarter
    return time_dict, quarter, end_of_quarter


def _league_time(league):
    """
    Return league specific game info -- number of quarters, regulation time
    limit, regular quarter length.
    """
    if(league == 'nba'):
        num_quarters = 4
        regulation_time = 48
        regular_quarter = 12
    else:
        num_quarters = 2
        regulation_time = 40
        regular_quarter = 20
    return num_quarters, regulation_time, regular_quarter


def _calc_overall_time(seconds, minutes, quarter, league):
    """
    Calculate the overall time that's elapsed for a given game. I'm not a fan
    of four arguments, but it's necessary unfortunately.
    """
    num_quarters, regulation_time, regular_quarter = _league_time(league)
    if quarter >= num_quarters:
        # We're in overtime.
        quarter_length = 5
        overtimes = quarter - num_quarters
        previous_time = datetime.timedelta(minutes=(regulation_time +
            5 * (overtimes - 1)))
    else:
        quarter_length = regular_quarter
        previous_time = datetime.timedelta(minutes=(quarter_length *
            (quarter - 1)))
    mins = datetime.timedelta(minutes=quarter_length) -\
            datetime.timedelta(minutes=minutes, seconds=seconds)
    overall_time = str(mins + previous_time)
    return overall_time


def _play_as_dict(play):
    """
    Give it a play in list/tuple format, get back a dict containing
    official_play, home_play, and away_play data.

    Really only for internal use with adjust_game.
    """
    # TODO: Play can be '&nbsp;' or u'\xa0', so I put len < 10.
    # Should probably change to something more explicit in the future.
    new_play = {}
    logo = str(play.find('td', {'class': 'logo'}))
    logo = (re.search('(?<=500/).+?(?=.png&amp;h=100&amp;w=100)', logo).group(0)).upper()
    if(logo != away_team):
        new_play['away_play'] = ""
        new_play['home_play'] = play.find('td', {'class': 'game-details'}).text
    else:
        new_play['away_play'] = play.find('td', {'class': 'game-details'}).text
        new_play['home_play'] = ""
    return new_play


def parse_plays(game_id, league='nba'):
    """Parse a game's Play-By-Play page on ESPN."""
    league = league.lower()
    espn = 'http://espn.com/' + league + '/playbyplay?gameId=' +\
            game_id
    url = urlopen(espn)
    soup = bs(url.read(), 'lxml')
    table = soup.find('div', {'id': 'gamepackage-qtrs-wrap'})
    #added exception in case playbyplay ain't available
    '''try:
        thead = [thead.extract() for thead in table.findAll('thead')]
        print(thead)
    except AttributeError:
        print ('\nPlay-By-Play not available :(\n')'''
    global title
    title = [team.extract() for team in soup.findAll('td', {'class': 'team-name'})]
    global away_team
    away_team = title[0].text
    global home_team
    home_team =  title[1].text
    rows = [tr.extract() for tr in table.findAll('tr')]
    del rows[0]
    game = adjust_game(rows, league)
    print('\n'+away_team+' @ '+home_team+', '+str(len(game))+' possessions')
    print(url.geturl())
    return away_team, home_team, game


def get_games(day, league='nba', iterable=False):
    """
    Get the games and play-by-play data from ESPN for a date.
    The date can be in `datetime.date` format or be a YYYYMMDD string.

    By default it only looks for NBA games on a date. You can modify
    this by passing it a league='ncb' argument to scrape the NCAA men's
    basketball games that have Play-By-Play data (NOTE: not all will).

    You can pass it an optional `iterable=True` argument in order to receive
    back a generator instead of the default list.
    """
    espn_scoreboard = _format_scoreboard_url(day, league=league)
    all_games = scrape_links(espn_scoreboard)
    if not iterable:
        games = [parse_plays(game, league=league) for game in all_games]
    else:
        games =  (parse_plays(game, league=league) for game in all_games)
    return games


def main():
    yesterday = datetime.date.today() - datetime.timedelta(1)
    for game in get_games(yesterday, iterable=True):
        print(game)

if __name__ == '__main__':
    import time
    start = time.time()
    main()
    print (time.time() - start, 'seconds')
