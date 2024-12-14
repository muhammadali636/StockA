import requests
from urllib.parse import quote
import yfinance as yf
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import time
from transformers import pipeline
from langdetect import detect

#make sure VADER lexicon is downloaded. Use nltk.download() in Python with/without Jupyter:
nltk.download('vader_lexicon') 
#init sentiment analyzer
sia = SentimentIntensityAnalyzer() 

#Init Hugging Face zero-shot classification model.
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

#headers so it looks like an agent. Makes sure reddit doesnt block us.
headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9'
}

#functions

#Checks if stock is a valid ticker from yfinance. 
def is_valid_ticker(ticker):
    try:
        stock = yf.Ticker(ticker.upper())
        return stock.info.get('symbol', '').upper() == ticker.upper()
    except Exception as e:
        print(e) #print exception 
        return False

#Get posts from a subreddit
def fetch_reddit_posts(stock, time_filter, subreddit):
    url = f'https://www.reddit.com/r/{subreddit}/search.json?q={quote(stock)}&sort=top&t={time_filter}&limit=50'
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            print(response.status_code)
            return []
        return response.json().get('data', {}).get('children', [])
    #network error
    except requests.exceptions.RequestException as e: 
        print(e)  #prints just the exception message
    #error decoding json
    except ValueError as e:
        print(e)  
    #other exceptions.
    except Exception as e:
        print(e)  
    return []
#filter posts for relevance using Hugging Face zero-shot classification
def is_relevant(content, stock):
    labels = [f"related to {stock} stock analysis", "not related to stock analysis"]
    result = classifier(content, labels)
    return result["labels"][0] == f"related to {stock} stock analysis"

#check if content is in English (a constraint)
def is_english(content):
    try:
        return detect(content) == "en"
    except:
        return False

#remove dupes posts based on the URL.
def remove_dupes(posts):
    unique_urls = set()
    unique_posts = []
    for post in posts:
        if post['url'] not in unique_urls:
            unique_urls.add(post['url'])
            unique_posts.append(post)
    return unique_posts

#main
def main():
    while (True):
        stock = input("Enter the stock symbol or keyword to search: ").strip().upper()
        time_filter = input("Enter time filter (day, week, month, year, all): ").strip().lower()

        if time_filter not in ["day", "week", "month", "year", "all"] or not is_valid_ticker(stock):
            print("Invalid input. Please try again.")
            continue
        break

    subreddits = [
        'wallstreetbets', 'pennystocks', 'valueinvesting',
        'investing', 'stockmarket', 'stocksandtrading',
        'robinhoodpennystocks', 'wallstreetbetselite', 
        'shortsqueeze', 'dividends'
    ]
    posts_data = []

    for subreddit in subreddits:
        print(f"\nSearching in r/{subreddit}...")
        posts = fetch_reddit_posts(stock, time_filter, subreddit)

        for post in posts:
            post_data = post.get('data', {})
            title = post_data.get('title', 'No Title')
            post_url = f"https://www.reddit.com{post_data.get('permalink', '')}"
            content = post_data.get('selftext', 'No Content')

            #skip posts with no content or less than 50 words (nonsense posts).
            #TODO: for future, perhaps we shouldnt hardcode this. 
            if content == 'No Content' or len(content.split()) < 50:
                continue

            #skip anything that isnt english
            if not is_english(content):
                print(f"...")
                continue

            #skip posts that arent relevant to the stock using Hugging Face model (transformers)
            if not is_relevant(content, stock):
                print(f"...")
                continue

            #analyze content sentiment for post that made it.
            content_sentiment = sia.polarity_scores(content)

            #append data
            posts_data.append({
                'subreddit': subreddit,
                'title': title,
                'url': post_url,
                'content_sentiment': content_sentiment
            })

        time.sleep(2) #so i dont get blocked.

    #remove dupes
    posts_data = remove_dupes(posts_data)

    #display if found
    if posts_data:
        print("\n--- Analysis Results ---\n")
        for post in posts_data:
            print(f"Subreddit: r/{post['subreddit']}")
            print(f"Title: {post['title']}")
            print(f"Post URL: {post['url']}")
            print(f"Content Sentiment: {post['content_sentiment']}")
            print("-" * 80)
    #if nothing is found
    else:
        print("\nNo valid posts found.")

main()




