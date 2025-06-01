import os
import sys
import argparse
import requests
import shlex

def fetch_json(url: str, token: str):
    headers = {"Authorization": token}
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def list_players(base_url: str, token: str):
    # Fetch teams to collect player IDs
    teams = fetch_json(f"{base_url}/teams", token)
    player_ids = set()
    for team in teams:
        for pid in team.get('players', []):
            player_ids.add(pid)
    # Fetch each player and collect full names
    names = []
    for pid in player_ids:
        try:
            pl = fetch_json(f"{base_url}/players/{pid}", token)
        except requests.HTTPError:
            continue
        parts = [pl.get('name', '').strip(), pl.get('surname', '').strip()]
        full = ' '.join([p for p in parts if p])
        if full:
            names.append(full)
    for name in sorted(set(names)):
        print(name)
    return teams  # return raw teams list for later use

def compute_stats(matches, team_id):
    wins = losses = goals_for = goals_against = 0
    for m in matches:
        t1 = m['team1']; t2 = m['team2']
        s1 = m['team1_score']; s2 = m['team2_score']
        if t1 == team_id or t2 == team_id:
            # determine this team's score
            if t1 == team_id:
                gf, ga = s1, s2
            else:
                gf, ga = s2, s1
            goals_for += gf; goals_against += ga
            if gf > ga:
                wins += 1
            elif gf < ga:
                losses += 1
    diff = goals_for - goals_against
    return wins, losses, diff

def handle_queries(base_url: str, token: str, teams, matches):
    # build name->id map
    team_map = {t['name']: t['id'] for t in teams}
    # build player->team map
    player_team = {}
    for t in teams:
        for pid in t.get('players', []):
            player_team[pid] = t['id']
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line.startswith('stats?'):
            # parse stats? "Team Name"
            rest = line[len('stats?'):].strip()
            try:
                name = shlex.split(rest)[0]
            except Exception:
                print('0 0 0')
                continue
            tid = team_map.get(name)
            if tid is None:
                print('0 0 0')
            else:
                w, l, d = compute_stats(matches, tid)
                # format diff with sign
                diff_str = f"{d:+d}"
                print(f"{w} {l} {diff_str}")
        elif line.startswith('versus?'):
            # parse versus? id1 id2
            parts = line[len('versus?'):].strip().split()
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                print('0')
                continue
            p1, p2 = map(int, parts)
            # verify players exist
            exists = True
            for pid in (p1, p2):
                try:
                    fetch_json(f"{base_url}/players/{pid}", token)
                except requests.HTTPError:
                    exists = False
                    break
            if not exists:
                print('0')
                continue
            t1 = player_team.get(p1)
            t2 = player_team.get(p2)
            if t1 is None or t2 is None:
                print('0')
                continue
            cnt = 0
            for m in matches:
                if (m['team1'] == t1 and m['team2'] == t2) or (m['team1'] == t2 and m['team2'] == t1):
                    cnt += 1
            print(cnt)
        else:
            # unknown command
            print('Unrecognized query', file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description='Sports stats client')
    parser.add_argument('--token', help='Authorization token (64-char)')
    parser.add_argument('--api-url', default='https://lksh-enter.ru', help='Base URL of the API')
    args = parser.parse_args()
    token = args.token or os.getenv('LKSH_TOKEN')
    if not token:
        print(
            'Error: Authorization token not provided. Obtain a plain-token from tg@lksh_p_2025_bot and pass it via --token or LKSH_TOKEN environment variable.',
            file=sys.stderr)
        sys.exit(1)
    # fetch data
    try:
        matches = fetch_json(f"{args.api_url}/matches", token)
    except Exception as e:
        print(f'Failed to fetch matches: {e}', file=sys.stderr)
        sys.exit(1)
    teams = None
    try:
        teams = list_players(args.api_url, token)
    except Exception as e:
        print(f'Failed to list players: {e}', file=sys.stderr)
        sys.exit(1)
    # handle queries
    handle_queries(args.api_url, token, teams, matches)


if __name__ == "__main__":
    main()