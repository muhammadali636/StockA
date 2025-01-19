import os
import matplotlib
matplotlib.use('Agg')  #Agg backend for headless environments
import matplotlib.pyplot as plt
from datetime import datetime
from collections import defaultdict
import yfinance as yf
import pandas as pd
import math

from django.conf import settings  # <-- ADDED to access MEDIA_ROOT

#plot showing "total post counts and average stock volume over the last 12 months"
def generate_post_counts_volume_plot(posts_data, stock):
    today = datetime.today()
    months = [(today - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(11, -1, -1)] #list of the last 12 months + the current month
    post_counts_by_month = defaultdict(int)
    for post in posts_data:
        post_date = post.get('date')
        if post_date:
            month = post_date.strftime('%Y-%m')
            if month in months:
                post_counts_by_month[month] += 1
    post_counts = [post_counts_by_month.get(month, 0) for month in months]
    
    #avg stock volume PERmonth
    stock_df = yf.download(stock, period='1y', interval='1mo', progress=False) 
    if stock_df.empty:
        avg_volumes = [0] * 12
    else:
        stock_df = stock_df.reset_index()
        stock_df['Month'] = stock_df['Date'].dt.strftime('%Y-%m')
        avg_volumes_dict = {}
        #average calculation
        for month in months:
            month_df = stock_df[stock_df['Month'] == month]
            if not month_df.empty:
                avg_volume = month_df['Volume'].mean()
                try:
                    avg_volume = float(avg_volume)  
                except (ValueError, TypeError):
                    avg_volume = None
                avg_volumes_dict[month] = avg_volume
            else:
                avg_volumes_dict[month] = None
        #none issue replace with 0
        avg_volumes = []
        last_valid = 0
        for month in months:
            volume = avg_volumes_dict.get(month, None)
            if volume is None or math.isnan(volume):
                volume = last_valid
            else:
                last_valid = volume
            avg_volumes.append(volume)

    fig, ax1 = plt.subplots(figsize=(12, 6))#makes plot reuse later.

    #BAR plot for post counts. 
    ax1.bar(range(len(months)), post_counts, color='lightgreen', label='Total Posts')
    ax1.set_xlabel('Month')
    ax1.set_ylabel('Total Posts', color='lightgreen')
    ax1.tick_params(axis='y', labelcolor='lightgreen')
    ax1.set_xticks(range(len(months)))
    ax1.set_xticklabels(months, rotation=45)

    #LINE PLOT FOR VOLUME AVG 
    ax2 = ax1.twinx()
    ax2.plot(range(len(months)), avg_volumes, color='purple', marker='o', label='Average Volume')
    ax2.set_ylabel('Average Volume', color='purple')
    ax2.tick_params(axis='y', labelcolor='purple')

    #TITLE AND LEGEND
    plt.title(f'Total Posts in Selected Subreddits and Average Volume for {stock} Over the Last 12 Months')
    fig.tight_layout()
    bars, labels_bars = ax1.get_legend_handles_labels()
    lines, labels_lines = ax2.get_legend_handles_labels()
    ax1.legend(bars + lines, labels_bars + labels_lines, loc='upper left')

    plot_filename = 'post_counts_avg_volume.png' #save
    # Use MEDIA_ROOT instead of 'static'
    plot_path = os.path.join(settings.MEDIA_ROOT, plot_filename)
    plt.savefig(plot_path)
    plt.close()
    return plot_filename
