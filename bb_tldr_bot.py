#!/usr/bin/env python3

import os
import re
import json
import praw
import sqlite3
import requests
import urllib.parse

api_key = os.environ.get("API_KEY")
api_url = "https://api.smmry.com"

reddit_username = "bb_tldr_bot"
reddit_password = os.environ.get("REDDIT_PASSWORD")
reddit_client_id = os.environ.get("REDDIT_CLIENT_ID")
reddit_client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

deny_list = ["www.reddit.com", "youtu.be", "github.com", "hackerone.com"]


def sqlite_connect():
    con = sqlite3.connect("reddit_data.db")
    cur = con.cursor()
    return con, cur


def reddit_api_auth():
    reddit = praw.Reddit(
        client_id=reddit_client_id,
        client_secret=reddit_client_secret,
        user_agent="bb_tldr_bot (by u/_vavkamil_)",
        username=reddit_username,
        password=reddit_password,
    )

    return reddit


def check_submissions(reddit):
    i = 0
    feed_dict = {}

    subreddit = reddit.subreddit("bugbounty")

    for submission in reddit.subreddit("bugbounty").new(limit=10):

        hostname = urllib.parse.urlparse(submission.url).netloc

        if hostname not in deny_list:
            feed_dict[i] = {}
            feed_dict[i]["reddit_id"] = submission.id
            feed_dict[i]["post_url"] = submission.url
            i = i + 1

    return feed_dict


def check_duplicates(feed_dict):
    con, cur = sqlite_connect()

    for k, v in list(feed_dict.items()):
        reddit_id = feed_dict[k]["reddit_id"]
        post_url = feed_dict[k]["post_url"]

        cur.execute(
            f"SELECT * FROM reddit WHERE reddit_id = (?)",
            [reddit_id],
        )
        con.commit()
        if cur.fetchone() == None:
            print(
                f"[i] New post: https://www.reddit.com/r/bugbounty/comments/{reddit_id}\n"
            )

            cur.execute(
                f"INSERT INTO reddit (reddit_id) VALUES (?)",
                [reddit_id],
            )
            con.commit()
        else:
            del feed_dict[k]

    con.close()

    return feed_dict


def get_smmry(feed_dict):
    i = 0
    smmry_dict = {}

    for k, v in list(feed_dict.items()):
        reddit_id = feed_dict[k]["reddit_id"]
        post_url = feed_dict[k]["post_url"]

        res = requests.get(
            f"{api_url}/?SM_API_KEY={api_key}&SM_LENGTH=3&SM_KEYWORD_COUNT=5&SM_WITH_BREAK&SM_URL={post_url}"
        )

        if res.status_code != 200:
            print(f"[!] HTTP status {res.status_code}")
            print(f"[!] Error parsing: {post_url}\n")
        else:
            json_obj = res.json()

            title = json_obj["sm_api_title"]
            reduced = json_obj["sm_api_content_reduced"]
            content = json_obj["sm_api_content"]
            keywords = ", ".join(json_obj["sm_api_keyword_array"])

            smmry_dict[i] = {}
            smmry_dict[i]["reddit_id"] = reddit_id
            smmry_dict[i]["post_url"] = post_url
            smmry_dict[i]["title"] = title
            smmry_dict[i]["reduced"] = reduced
            smmry_dict[i]["content"] = content
            smmry_dict[i]["keywords"] = keywords

    return smmry_dict


def post_to_reddit(reddit, smmry_dict):
    for k, v in list(smmry_dict.items()):
        reddit_id = smmry_dict[k]["reddit_id"]
        post_url = smmry_dict[k]["post_url"]
        title = smmry_dict[k]["title"]
        reduced = smmry_dict[k]["reduced"]
        content = smmry_dict[k]["content"]
        keywords = smmry_dict[k]["keywords"]

        content = content.replace("[BREAK] ", "\n\n> ")
        content = content.replace("[BREAK]", "")

        submission = reddit.submission(id=reddit_id)

        reply_template = """## {}
This is the best tl;dr I could make, [original]({}) reduced by {}. (I'm a bot)

---

> {}

---

[Summary Source](https://smmry.com/{}) | [**Source code**](https://github.com/vavkamil/bb_tldr_bot) | [Feedback](http://www.reddit.com/message/compose?to=%5Fvavkamil%5F) | Keywords: **{}**
"""

        reply_text = reply_template.format(
            title, post_url, reduced, content, post_url, keywords
        )
        submission.reply(reply_text)


def main():
    print("[ bb_tldr_bot ]\n\n")

    print("[i] Authenticate to Reddit's API\n")
    reddit = reddit_api_auth()

    print("[i] Check new submissions\n")
    feed_dict = check_submissions(reddit)

    print("[i] Check for duplicates\n")
    feed_dict = check_duplicates(feed_dict)

    if len(feed_dict) == 0:
        print("[i] No new posts\n")
    else:
        print(f"[i] Found {len(feed_dict)} new posts\n")

        print(f"[i] Get smmry\n")
        smmry_dict = get_smmry(feed_dict)
        print(f"[i] Summarized {len(smmry_dict)} new posts\n")

        print("[i] Post to Reddit\n")
        post_to_reddit(reddit, smmry_dict)


if __name__ == "__main__":
    main()
