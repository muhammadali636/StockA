import os
import requests
import yfinance as yf
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import time
from langdetect import detect
import pandas as pd
from collections import defaultdict
from datetime import datetime, timedelta

nltk.download('vader_lexicon')#download vader for sent analysis.
VADER = SentimentIntensityAnalyzer()#sent analy sis.

TIME_FILTER_MAPPING = {'day': '5d','week': '5d','month': '1mo','year': '1y','all': 'max'}
headers = {'User-Agent': 'Mozilla/5.0 (compatible; Bot/0.1)'} #so reDdit doesnt blocp for scraping MORE: (https://deviceatlas.com/blog/list-of-user-agent-strings).

        #       get stock metrics + average daily change + last close value
def get_stock_metrics(ticker, period='3mo'):
    df_today = yf.download(ticker, period='1d', interval='1d', progress=False)
    if df_today.empty:
        current_total_volume = 0
        stock_price_today = 0.0
    else:
        current_total_volume = int(df_today['Volume'].iloc[-1].item())   #SINGLE ELEMENT SERIES
        stock_price_today = float(df_today['Close'].iloc[-1].item())

    today = datetime.now().date()
    target_date = today - timedelta(days=31)
    df_past = yf.download(ticker, start=(target_date - timedelta(days=1)).strftime('%Y-%m-%d'), end=(today + timedelta(days=1)).strftime('%Y-%m-%d'), interval='1d', progress=False)

    if df_past.empty:
        close_past = 0.0
        volume_past = 0.0
    else:
        df_past_filtered = df_past[df_past.index.date <= target_date]
        if df_past_filtered.empty:
            close_past = 0.0
            volume_past = 0.0
        else:
            closest_date = df_past_filtered.index.max()
            close_past = float(df_past['Close'].loc[closest_date].item())
            volume_past = float(df_past['Volume'].loc[closest_date].item())

    if close_past != 0:
        stock_price_change_pct = ((stock_price_today - close_past) / close_past) * 100.0
    else:
        stock_price_change_pct = 0.0

    if volume_past != 0:
        volume_change_pct = ((current_total_volume - volume_past) / volume_past) * 100.0
    else:
        volume_change_pct = 0.0

    df_period = yf.download(ticker, period=period, interval='1d', progress=False)
    if df_period.empty or len(df_period) < 2:
        avg_daily_change = 0.0
    else:
        avg_daily_change = df_period['Close'].pct_change().mean() * 100.0
    return {
        'avg_daily_change': round(avg_daily_change, 2), 'stock_price': round(stock_price_today, 2), 'current_total_volume': current_total_volume, 'volume_change_pct': round(volume_change_pct, 2), 'stock_price_change_pct': round(stock_price_change_pct, 2)
    }

#       func to check if user entered ticker symbol is valid using yfin API
def is_valid_ticker(ticker):
    stock = yf.Ticker(ticker.upper())
    symbol = stock.info.get('symbol', '')
    if symbol and symbol.upper() == ticker.upper():
        return True
    return False

#VADER sentiment (neg, neu, pos, compound) and conver tthat to either POSITIVE, NEGATIVE, NEUTRAL.
def label_sentiment(compound_score):
    if compound_score > 0.5:
        return "POSITIVE"
    elif compound_score < -0.5:
        return "NEGATIVE"
    else:
        return "NEUTRAL"

#get posts from a specific subreddit based on the stock ticker and time filter
def fetch_reddit_posts(stock, subreddit, time_filter="all", sort="top", max_results=1000, per_page=100):
    base_url = f"https://www.reddit.com/r/{subreddit}/search.json" #look up subreddit by name,  
    all_posts = []
    after = None
    while True:
        params = {"q": stock, "restrict_sr": "true", "sort": sort, "t": time_filter,"limit": per_page,}
        if after:
            params["after"] = after
        try:
            response = requests.get(base_url, headers=headers, params=params)
            if response.status_code != 200:
                break
            data = response.json().get("data", {})
            children = data.get("children", [])
            if not children:
                break
            all_posts.extend(children)
            if len(all_posts) >= max_results:
                break
            after = data.get("after")
            if not after:
                break
            time.sleep(1.0)            #prevent rate-limiting by Reddit stay stealthy.
        except:
            break
    return all_posts[:max_results]

#only english via langdetect lib.
def is_english(content):
    try:
        return detect(content) == "en"
    except:
        return False

#dupe post remover.
def remove_dupes(posts):
    unique_urls = set()
    unique_posts = []
    for post in posts:
        post_url = post.get('url')
        if post_url and post_url not in unique_urls:
            unique_urls.add(post_url)
            unique_posts.append(post)
    return unique_posts

#post scraper
def scrape_posts(stock, time_filter, subreddits, period):
    #validate time_filter
    if time_filter not in ["day", "week", "month", "year", "all"]:
        return [], {}, None
    period = TIME_FILTER_MAPPING.get(time_filter, '1mo')
    if not is_valid_ticker(stock):
        return [], {}, None
    metrics = get_stock_metrics(stock, period=period)
    if not metrics:
        return [], {}, None
    posts_data = []
    all_compounds = []

    #relevancy to specified stock can also modify this to look for due diligence specifically on reddit (prob a better idea tbh.)  USE TRANSFORMERS INSTEAD OF OPENAI API
    #def is_relevant(content, stock):
    #         stream = client.chat.completions.create(
    #             model="gpt-4o", 
    #             messages=[
    #                 {"role": "system", "content": "classify text as relevant or not to a stock."},
    #                 {"role": "user", "content": f"Is this text about {stock} stock?\n{content}\n."}
    #             ],
    #             stream = True,

    #Summarizes multiple posts into one paragraph  KEEP OPENAI 
    #PROBLEM OPENAI API IS NOT FREE FOR LATER
    #TODO might have 10000 posts and chatgpt has a limit, limit this to the recent 100 posts. or we can filter better for due diligence (see above)
    #def summarize_posts(posts, stock):
    #         combined_content = " ".join([f"{post['title']}. {post['content_sentiment']['compound']}" for post in posts])
    #         stream = client.chat.completions.create(
    #             model="gpt-4o",
    #             messages=[
    #                 {"role": "system", "content": "You summarize text."},
    #                 {"role": "user", "content": f"Summarize posts about {stock}: {combined_content}"}
    #             ],
    #             stream=True,
    
    for subreddit in subreddits:
        raw_posts = fetch_reddit_posts(stock, subreddit, time_filter, "top", 1000, 100)
        for rp in raw_posts:
            post_data = rp.get('data', {})
            title = post_data.get('title', 'No Title')
            permalink = post_data.get('permalink', '')
            post_url = f"https://www.reddit.com{permalink}"
            content = post_data.get('selftext', 'No Content')
            created_utc = post_data.get('created_utc', 0)
            #skip any posts with not enough content or non-English text
            if content == 'No Content' or len(content.split()) < 50:
                continue
            if not is_english(content):
                continue

            
            #LATER: to filter with  relevancy constraints using TRANSFORMERS BERT   etc:
                    # if not is_relevant(content, stock):
                    #     continue
            sentiment_dict = VADER.polarity_scores(content)   #VADER sentiment (neg, neu, pos, compound) and conver tthat to either POSITIVE, NEGATIVE, NEUTRAL.
            sentiment_label = label_sentiment(sentiment_dict['compound'])
            all_compounds.append(sentiment_dict['compound'])
            post_date = datetime.utcfromtimestamp(created_utc).date()
            posts_data.append({'subreddit': subreddit,'title': title,'url': post_url,'compound_score': sentiment_dict['compound'],'content_sentiment': sentiment_label,'date': post_date})
        time.sleep(1.0)    #prevent rate-limiting by Reddit stay stealthy.
    posts_data = remove_dupes(posts_data)
    if all_compounds:
        overall_label = label_sentiment(sum(all_compounds) / len(all_compounds))
    else:
        overall_label = None
    return posts_data, metrics, overall_label
