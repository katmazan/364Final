import praw
import settings
import json
reddit = praw.Reddit(client_id=settings.red_client,
                     client_secret= settings.red_secret,
                     user_agent='User Agent:script:python.my.data.collection:v1.2.3 (by /u/katarain)')

##Retrives the first two "Hot" Post from inputted subreddit//sample inputs could be any subreddit "Indieheads", "Overwatch"
##Subreddits and their top 5 posts will be saved in the Subreddit and Post db table
def hot_posts(sub):
    
    
    red = reddit.subreddit(sub).hot(limit=5)
    for thing in red:
        print(thing.title)


##Retrives a list of subreddits that follow the topic the user inputs//sample inputs could be: Music, Sports, Movies
##Topics will be saves in the Topic db table and Subreddits will be saved in teh Subreddit db table
def search_topic(topic):
   
    blah = reddit.subreddits.search_by_topic(topic)
    for thing in blah:
        print(thing.title).type()

hot_posts('Overwatch')
print('\n','\n')
hot_posts('Indieheads')
print('\n','\n')
search_topic('music')
print('\n','\n')
search_topic('cats')