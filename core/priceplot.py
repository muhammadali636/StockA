import os
import matplotlib
matplotlib.use('Agg')  # Use Agg backend for headless environments
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict
import yfinance as yf
import pandas as pd
import math

from django.conf import settings  # <-- ADDED to access MEDIA_ROOT

#1) generate matplotlib for post counts and stock prices 
def generate_post_counts_stock_plot(posts_data, stock):     
    today = datetime.today()
    #list of last 12 months including this month
    months = [(today - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(11, -1, -1)]
    post_counts_by_month = defaultdict(int)
    for post in posts_data:
        post_date = post.get('date')
        if post_date:
            month = post_date.strftime('%Y-%m')
            if month in months:
                post_counts_by_month[month] += 1 #count post by moht
    post_counts = [post_counts_by_month.get(month, 0) for month in months]

    #stock prices at the end of each month with yfinance
    stock_df = yf.download(stock, period='1y', interval='1d', progress=False)
    if stock_df.empty:
        stock_prices = [0] * 12
    else:
        stock_df = stock_df.reset_index()
        stock_df['Month'] = stock_df['Date'].dt.strftime('%Y-%m')
        #last trading day of each month
        stock_prices_dict = {}
        for month in months:
            month_df = stock_df[stock_df['Month'] == month]
            if not month_df.empty:
                last_day_close = month_df.iloc[-1]['Close']
                try:
                    last_day_close = float(last_day_close)  
                except (ValueError, TypeError):
                    last_day_close = None
                stock_prices_dict[month] = last_day_close
            else:
                stock_prices_dict[month] = None
        #none issue replace with with previous month's price or 0
        stock_prices = []
        last_valid = 0
        for month in months:
            price = stock_prices_dict.get(month, None)
            if price is None or math.isnan(price):
                price = last_valid
            else:
                last_valid = price #the most recent valid price
            stock_prices.append(price)

    fig, ax1 = plt.subplots(figsize=(12, 6)) #makes plot

    #BAR PLOTS FOR TOTAL POST COUNT REUSE IN VOLUMEPLOT.PY
    ax1.bar(range(len(months)), post_counts, color='skyblue', label='Total Posts')
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Total Posts', color='skyblue')
    ax1.tick_params(axis='y', labelcolor='skyblue')
    ax1.set_xticks(range(len(months)))
    ax1.set_xticklabels(months, rotation=45)

    #LINE PLOT FOR STOCK PRICE
    ax2 = ax1.twinx()
    ax2.plot(range(len(months)), stock_prices, color='orange', marker='o', label='Stock Price')
    ax2.set_ylabel('Stock Price ($)', color='orange')
    ax2.tick_params(axis='y', labelcolor='orange')

    #TITLE AND LEGEND
    plt.title(f'Total Posts in Selected Subreddits and Stock Price for {stock} Over the Last 12 Months')
    fig.tight_layout()
    bars, labels_bars = ax1.get_legend_handles_labels()
    lines, labels_lines = ax2.get_legend_handles_labels()
    ax1.legend(bars + lines, labels_bars + labels_lines, loc='upper left')

    plot_filename = 'post_counts_stock_prices.png' #save 
    # Use MEDIA_ROOT instead of 'static'
    plot_path = os.path.join(settings.MEDIA_ROOT, plot_filename)
    plt.savefig(plot_path)
    plt.close()
    return plot_filename
