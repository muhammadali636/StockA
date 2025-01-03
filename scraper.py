
import requests 
from urllib.parse import quote
import yfinance as yf
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import time
from langdetect import detect

#import openai premium.
import os

nltk.download('vader_lexicon')#download vader for sent analysis.
VADER = SentimentIntensityAnalyzer()        #sent analysis.

#openai.api_key = os.getenv("OPENAI_API_KEY") save this for later since its not free anymore. Perhaps a premium version because openai no longer free. Or use a free LLM.
#get stock metrics including average daily change and last close value
def get_stock_metrics(ticker, period='1mo'):
    df = yf.download(ticker, period=period, interval='1d', progress=False)
    if len(df) == 0:
        return {}
    
    df['DailyChange'] = df['Close'].pct_change()
    last_close_value = float(df['Close'][len(df) - 1]) 
    avg_daily_change = sum(df['DailyChange']) / len(df['DailyChange']) * 100.0

    return {
        'avg_daily_change': avg_daily_change, 
        'last_close': last_close_value
    }

#function to check if user entered ticker symbol is valid using yfin API
def is_valid_ticker(ticker):
    try:
        stock = yf.Ticker(ticker.upper())
        return stock.info.get('symbol', '').upper() == ticker.upper()
    except Exception as e:
        print("Error validating the ticker:", e)
        return False

#relevancy to specified stock can also modify this to look for due diligence specifically on reddit (prob a better idea tbh.) 
#def is_relevant(content, stock):
#         stream = client.chat.completions.create(
#             model="gpt-4o", 
#             messages=[
#                 {"role": "system", "content": "classify text as relevant or not to a stock."},
#                 {"role": "user", "content": f"Is this text about {stock} stock?\n{content}\n."}
#             ],
#             stream = True,

#Summarizes multiple posts into one paragraph 
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

#VADER sentiment (neg, neu, pos, compound) and conver t that to either POSITIVE, NEGATIVE, NEUTRAL.
def label_sentiment(sentiment_dict):
    compound = sentiment_dict.get('compound', 0.0)
    if compound >= 0.05:
        return "POSITIVE"
    elif compound <= -0.05:
        return "NEGATIVE"
    else:
        return "NEUTRAL"

#get posts from a specific subreddit based on the stock ticker and time filter
def fetch_reddit_posts(stock, subreddit, time_filter="all", sort="top", max_results=1000, per_page=100):
    base_url = "https://www.reddit.com/r/{}/search.json".format(subreddit)
    all_posts = []
    after = None

    while True:
        params = {
            "q": stock,
            "restrict_sr": "true",
            "sort": sort,
            "t": time_filter,
            "limit": per_page,
        }
        if after:
            params["after"] = after
        try:
            response = requests.get(
                base_url,
                headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9'},
                params=params
            )
            if response.status_code != 200:
                print(f"Error {response.status_code} in r/{subreddit}")
                break
            data = response.json().get("data", {})
            children = data.get("children", [])
            if not children:
                break
            all_posts.extend(children)
            if len(all_posts) >= max_results:
                print(f"Reached max_results: {max_results}")
                break
            after = data.get("after")
            if not after:
                break
            time.sleep(1.0)  #prevent rate-limiting by Reddit stay stealthy.

        except Exception as e:
            print(f"Error fetching from subreddit '{subreddit}':", e)
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
        if post['url'] not in unique_urls:
            unique_urls.add(post['url'])
            unique_posts.append(post)
    return unique_posts

def scrape_posts(stock, time_filter, subreddits):
    # Validate time_filter
    if time_filter not in ["day", "week", "month", "year", "all"]:
        print("Invalid time filter.")
        return [], {}, None

    #validate ticker
    if not is_valid_ticker(stock):
        print("Invalid Ticker Symbol.")
        return [], {}, None

    metrics = get_stock_metrics(stock, period='1mo')
    posts_data = []
    all_compounds = []

    for subreddit in subreddits:
        raw_posts = fetch_reddit_posts(
            stock=stock,
            subreddit=subreddit,
            time_filter=time_filter,
            sort="top",
            max_results=1000
        )
        for rp in raw_posts:
            post_data = rp.get('data', {})
            title = post_data.get('title', 'No Title')
            permalink = post_data.get('permalink', '')
            post_url = f"https://www.reddit.com{permalink}"
            content = post_data.get('selftext', 'No Content')

            #skip any posts with insufficient content or non-English text
            if content == 'No Content' or len(content.split()) < 50:
                continue
            if not is_english(content):
                continue

            #LATER: to filter with  relevancy constraints:
            # if not is_relevant(content, stock):
            #     continue

            sentiment_dict = VADER.polarity_scores(content)
            sentiment_label = label_sentiment(sentiment_dict)
            all_compounds.append(sentiment_dict['compound'])

            posts_data.append({
                'subreddit': subreddit,
                'title': title,
                'url': post_url,
                'content_sentiment': sentiment_dict,
                'sentiment_label': sentiment_label
            })
        time.sleep(1.0)  #avoid Reddit rate-limiting stay stealthy.

    posts_data = remove_dupes(posts_data)


