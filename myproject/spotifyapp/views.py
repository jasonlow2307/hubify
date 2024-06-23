from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.conf import settings
from django.core.mail import send_mail
import requests
import logging
from collections import Counter
import urllib.parse
import boto3
from boto3.dynamodb.conditions import Attr

# Spotify API endpoints
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE_URL = "https://api.spotify.com/v1"

def index(request):
    logging.basicConfig(filename='spotify_api.log', level=logging.DEBUG)

    access_token = request.session.get('access_token')
    if not access_token:
        logging.error("Access token not found")
        return HttpResponse("Access token not found", status=500)

    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'limit': 10, 'time_range': 'medium_term'}

    # Fetch top tracks
    response = requests.get(f"{API_BASE_URL}/me/top/tracks", headers=headers, params=params)
    if response.status_code != 200:
        logging.error(f"Error fetching top tracks: {response.text}")
        return HttpResponse("Error fetching top tracks", status=500)
    top_tracks_data = response.json().get('items')
    artist_names = [track['artists'][0]['name'] for track in top_tracks_data]
    top_tracks = [
        {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
            'track_url': track['preview_url']
        }
        for track in top_tracks_data
    ]

    # Determine the top artist
    artist_counts = Counter(artist_names)
    top_artist_name, _ = artist_counts.most_common(1)[0]
    top_artist_data = next(track['artists'][0] for track in top_tracks_data if track['artists'][0]['name'] == top_artist_name)

    response = requests.get(f"{API_BASE_URL}/artists/{top_artist_data['id']}", headers=headers)
    top_artist = response.json()
    top_artist['image_url'] = top_artist['images'][0]['url']

    # Fetch recently played tracks
    response = requests.get(f"{API_BASE_URL}/me/player/recently-played", headers=headers, params=params)
    recently_played_data = response.json().get('items')
    recently_played_list = [
        {
            'name': track['track']['name'],
            'artist': track['track']['artists'][0]['name'],
            'image_url': track['track']['album']['images'][0]['url'] if track['track']['album']['images'] else None,
            'track_url': track['track']['preview_url']
        }
        for track in recently_played_data
    ]

    return render(request, 'index.html', {
        'top_artist': top_artist,
        'artist_counts': artist_counts.items(),
        'top_tracks': top_tracks,
        'recently_played': recently_played_list
    })

def login(request):
    return render(request, 'auth.html')

def topSongsQuery(request):
    return render(request, 'topSongsQuery.html')

def login_form(request):
    scope = 'user-top-read user-read-recently-played playlist-read-private playlist-read-collaborative playlist-modify-public playlist-modify-private user-read-email'
    params = {
        'client_id': settings.SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'scope': scope,
        'redirect_uri': settings.SPOTIFY_REDIRECT_URI
    }

    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

def callback(request):
    code = request.GET.get('code')
    if not code:
        return HttpResponse("Authorization code not found", status=500)

    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': settings.SPOTIFY_REDIRECT_URI,
        'client_id': settings.SPOTIFY_CLIENT_ID,
        'client_secret': settings.SPOTIFY_CLIENT_SECRET
    }
    response = requests.post(TOKEN_URL, data=data)
    if response.status_code != 200:
        return HttpResponse("Error fetching access token", status=500)

    tokens = response.json()
    request.session['access_token'] = tokens.get('access_token')
    request.session['refresh_token'] = tokens.get('refresh_token')

    # Fetch user email
    headers = {'Authorization': f'Bearer {tokens["access_token"]}'}
    response = requests.get(f"{API_BASE_URL}/me", headers=headers)
    user_email = response.json().get('email')

    # Check user registration
    dynamodb = boto3.resource('dynamodb', aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, region_name=settings.AWS_SES_REGION_NAME)
    table = dynamodb.Table('hubify-users')
    response = table.scan(FilterExpression=Attr('email').eq(user_email))

    if response['Count'] == 0:
        requestRegistration(user_email)
        return redirect('waiting_list')
    else:
        return redirect('index')

def requestRegistration(email):
    send_mail(
        'Request for registration',
        f'Please register this email: {email}\n\nhttps://developer.spotify.com/',
        'your_verified_email@example.com',
        ['recipient@example.com'],
        fail_silently=False,
    )

def waiting_list(request):
    return render(request, 'waitingList.html')

def get_top_songs(request):
    top_tracks, time_range = topSongsResult(request)
    access_token = request.session.get('access_token')
    return render(request, 'topSongsResult.html', {'songs': top_tracks, 'time_range': time_range, 'access_token': access_token})

def topSongsResult(request):
    logging.basicConfig(filename='spotify_api.log', level=logging.DEBUG)

    time_range = request.POST.get('time_range')
    access_token = request.session.get('access_token')
    if not access_token:
        logging.error("Access token not found")
        return HttpResponse("Access token not found", status=500)

    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'limit': 10, 'time_range': time_range}
    response = requests.get(f"{API_BASE_URL}/me/top/tracks", headers=headers, params=params)
    if response.status_code != 200:
        logging.error(f"Error fetching top tracks: {response.text}")
        return HttpResponse("Error fetching top tracks", status=500)

    top_tracks_data = response.json().get('items')
    top_tracks = [
        {
            'name': track['name'],
            'artist': track['artists'][0]['name'],
            'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
            'track_id': track['id'],
            'track_url': track['preview_url']
        }
        for track in top_tracks_data
    ]

    return top_tracks, time_range

def spotimatch(request):
    top_tracks, _ = topSongsResult(request)
    top_track = top_tracks[0]

    access_token = request.session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.get(f"{API_BASE_URL}/tracks/{top_track['track_id']}", headers=headers)
    current_track = response.json()
    current_track['image_url'] = current_track['album']['images'][0]['url']
    current_track['artist'] = current_track['artists'][0]

    response = requests.get(f"{API_BASE_URL}/me", headers=headers)
    user = response.json()

    return render(request, 'spotimatch.html', {
        'current_track': current_track,
        'top_tracks': top_tracks,
        'user': user,
        'access_token': access_token
    })

def gotify(request):
    access_token = request.session.get('access_token')
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response = requests.get(f"{API_BASE_URL}/me", headers=headers)
    user = response.json()

    context = {
        'AWS_ACCESS_KEY_ID': settings.AWS_ACCESS_KEY_ID,
        'AWS_SECRET_ACCESS_KEY': settings.AWS_SECRET_ACCESS_KEY,
        'AWS_SES_REGION_NAME': settings.AWS_SES_REGION_NAME,
    }

    return render(request, 'gotify.html', {'user': user, 'context': context, 'access_token': access_token})
