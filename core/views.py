from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.db import connection 
from django.views.decorators.csrf import csrf_exempt  
from werkzeug.security import generate_password_hash, check_password_hash
import os

from .scraper import scrape_posts, is_valid_ticker 
from .priceplot import generate_post_counts_stock_plot
from .volumeplot import generate_post_counts_volume_plot

TIME_FILTER_MAPPING = {
    'day': '1d',
    'week': '5d',
    'month': '1mo',
    'year': '1y',
    'all': 'max'
}

def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        with connection.cursor() as cur:
            cur.execute("SELECT 1 FROM users WHERE username = %s", [username])
            user_exists = cur.fetchone()
            if user_exists:
                messages.error(request, "Username already exists. Please try again.")
            else:
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", [username, hashed_password])
                messages.success(request, "Registration successful!")
                return redirect(reverse('login'))
    return render(request, 'register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        with connection.cursor() as cur:
            cur.execute("SELECT username, password FROM users WHERE username = %s", [username])
            result = cur.fetchone()
            if not result:
                messages.error(request, "User does not exist.")
                return redirect(reverse('login'))
            db_username, db_hashed_password = result
            if check_password_hash(db_hashed_password, password):
                # In Django, typically you use `request.session` for storing session data
                request.session['username'] = db_username
                messages.success(request, "Logged in successfully!")
                return redirect(reverse('home'))
            else:
                messages.error(request, "Wrong password.")
    return render(request, 'login.html')


def delete_view(request):
    if 'username' not in request.session:
        messages.error(request, "You must be logged in to delete your account!")
        return redirect(reverse('login'))

    if request.method == 'POST':
        username_form = request.POST.get('username', '').strip()
        password_form = request.POST.get('password', '').strip()
        current_session_user = request.session['username']
        if username_form != current_session_user:
            messages.error(request, "The username does not match the logged-in account.")
            return render(request, 'delete.html')

        with connection.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE username = %s", [current_session_user])
            result = cur.fetchone()

            if not result:
                messages.error(request, "User does not exist.")
                return redirect(reverse('login'))

            db_hashed_password = result[0]
            if check_password_hash(db_hashed_password, password_form):
                cur.execute("DELETE FROM users WHERE username = %s", [current_session_user])
                request.session.pop('username', None)
                messages.success(request, "Account deleted successfully, sorry to see you go :(")
                return redirect(reverse('login'))
            else:
                messages.error(request, "Invalid username or password.")

    return render(request, 'delete.html')


def update_view(request):
    if 'username' not in request.session:
        messages.error(request, "You must be logged in to update your password.")
        return redirect(reverse('login'))

    if request.method == 'POST':
        old_password = request.POST.get('old_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        username = request.session['username']

        with connection.cursor() as cur:
            cur.execute("SELECT password FROM users WHERE username = %s", [username])
            result = cur.fetchone()

            if not result:
                messages.error(request, "User does not exist.")
                return redirect(reverse('update'))

            db_hashed_password = result[0]

            if check_password_hash(db_hashed_password, old_password):
                if new_password == confirm_password:
                    hashed_new_password = generate_password_hash(new_password, method='pbkdf2:sha256')
                    cur.execute("UPDATE users SET password = %s WHERE username = %s", [hashed_new_password, username])
                    messages.success(request, "Password updated!")
                    return redirect(reverse('home'))
                else:
                    messages.error(request, "New passwords do not match.")
            else:
                messages.error(request, "Wrong old password.")

    return render(request, 'update.html')


def signout_view(request):
    request.session.pop('username', None)
    messages.success(request, "You have been logged out.")
    return redirect(reverse('login'))


def home_view(request):
    if 'username' not in request.session:
        messages.error(request, "You must be logged in to access this page.")
        return redirect(reverse('login'))

    stock = None
    posts_data = []
    metrics = {}
    overall_sentiment_label = None
    plot_prices = None
    plot_volume = None
    total_posts = 0
    timeframe_description = ""

    if request.method == 'POST':
        stock = request.POST.get('stock', '').strip().upper()
        time_filter = request.POST.get('time_filter', '').strip().lower()
        selected_subreddits = request.POST.getlist('subreddits')

        if not selected_subreddits:
            messages.warning(request, "Please select at least one subreddit.")
        elif not stock:
            messages.warning(request, "Please enter a stock symbol.")
        else:
            if not is_valid_ticker(stock):
                messages.warning(request, "Ticker not found.")
            else:
                period = TIME_FILTER_MAPPING.get(time_filter, '1mo')

                # 1) SCRAPE
                try:
                    posts_data, metrics, overall_sentiment_label = scrape_posts(
                        stock, time_filter, selected_subreddits, period
                    )
                except Exception as e:
                    messages.error(request, f"ERROR while scraping posts: {e}")
                    posts_data, metrics, overall_sentiment_label = [], {}, None

                if not posts_data and not metrics:
                    messages.warning(request, "No valid posts found or invalid inputs.")
                else:
                    total_posts = len(posts_data)

                # timeframe_description
                if period == '1mo':
                    timeframe_description = "1 Month"
                elif period == '1d':
                    timeframe_description = "1 Day"
                elif period == '5d':
                    timeframe_description = "5 Days"
                elif period == '1y':
                    timeframe_description = "1 Year"
                else:
                    timeframe_description = "All Time"

                # get 1 year worth of data for plots
                try:
                    plot_posts_data, _, _ = scrape_posts(stock, 'year', selected_subreddits, '1y')
                except Exception as e:
                    messages.error(request, f"ERROR while scraping data for 12-month plot: {e}")
                    plot_posts_data = []

                if plot_posts_data:
                    try:
                        plot_prices = generate_post_counts_stock_plot(plot_posts_data, stock)
                    except Exception as e:
                        messages.error(request, f"ERROR generating the stock plot: {e}")
                        plot_prices = None

                    try:
                        plot_volume = generate_post_counts_volume_plot(plot_posts_data, stock)
                    except Exception as e:
                        messages.error(request, f"ERROR generating the volume plot: {e}")
                        plot_volume = None

    return render(request, 'home.html', {
        'stock': stock,
        'posts_data': posts_data,
        'metrics': metrics,
        'overall_label': overall_sentiment_label,
        'plot_prices': plot_prices,
        'plot_volume': plot_volume,
        'total_posts': total_posts,
        'timeframe_description': timeframe_description,
    })
