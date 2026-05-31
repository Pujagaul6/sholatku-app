from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, session
import sqlite3
import os
import json
import hashlib
import time
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)
app.secret_key = 'sholatku-secret-2026'
DB_PATH = '/home/ubuntu/sholat-app/sholatku.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    # Mosques table
    c.execute('''CREATE TABLE IF NOT EXISTS mosques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        lat REAL,
        lon REAL,
        city TEXT,
        phone TEXT,
        description TEXT,
        imam_name TEXT,
        capacity INTEGER,
        facilities TEXT,
        photo_url TEXT,
        dkm_user_id INTEGER,
        verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # DKM Users table
    c.execute('''CREATE TABLE IF NOT EXISTS dkm_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        mosque_id INTEGER,
        name TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mosque_id) REFERENCES mosques(id)
    )''')

    # Events table
    c.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mosque_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        event_type TEXT,
        event_date TEXT,
        event_time TEXT,
        is_recurring INTEGER DEFAULT 0,
        recurrence TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mosque_id) REFERENCES mosques(id)
    )''')

    # Reviews table
    c.execute('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mosque_id INTEGER NOT NULL,
        user_name TEXT,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mosque_id) REFERENCES mosques(id)
    )''')

    # Donations table
    c.execute('''CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mosque_id INTEGER NOT NULL,
        donor_name TEXT,
        amount REAL NOT NULL,
        message TEXT,
        payment_method TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mosque_id) REFERENCES mosques(id)
    )''')

    # Suggest Mosque table
    c.execute('''CREATE TABLE IF NOT EXISTS suggest_mosques (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        lat REAL,
        lon REAL,
        city TEXT,
        suggester_name TEXT,
        suggester_phone TEXT,
        notes TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS suggest_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mosque_id INTEGER,
        mosque_name TEXT,
        title TEXT NOT NULL,
        description TEXT,
        event_type TEXT,
        event_date TEXT,
        event_time TEXT,
        suggester_name TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Seed some mosques if empty
    c.execute("SELECT COUNT(*) FROM mosques")
    if c.fetchone()[0] == 0:
        seed_mosques(c)

    conn.commit()
    conn.close()

def seed_mosques(c):
    mosques = [
        ('Masjid Agung Tulungagung', 'Jl. I Gusti Ngurah Rai, Tulungagung', -8.0657, 111.9035, 'Tulungagung',
         'Masjid utama Kabupaten Tulungagung, sering mengadakan kajian besar', 'KH. Ahmad Fauzi', 2000,
         'AC, Parkir Luas, Perpustakaan, Tempat Wudhu Pria/Wanita, Ruang Ibu & Anak'),
        ('Masjid Al-Ikhlas', 'Jl. Diponegoro, Tulungagung', -8.0680, 111.9050, 'Tulungagung',
         'Masjid lingkungan dengan kegiatan rutin harian', 'Ust. Hidayat', 500,
         'Parkir, Tempat Wudhu, Sound System'),
        ('Masjid Jami\' Baiturrahman', 'Jl. Sultan Agung, Tulungagung', -8.0640, 111.9020, 'Tulungagung',
         'Masjid bersejarah di pusat kota', 'KH. Sholeh', 800,
         'AC, Parkir, Perpustakaan, Ruang Kajian'),
        ('Masjid Al-Hikmah', 'Jl. Panglima Sudirman, Tulungagung', -8.0695, 111.9065, 'Tulungagung',
         'Masjid dekat pasar, aktif kegiatan sosial', 'Ust. Rahmat', 300,
         'Parkir, Tempat Wudhu, Dapur Umum'),
        ('Masjid Nurul Iman', 'Jl. Veteran, Tulungagung', -8.0620, 111.9010, 'Tulungagung',
         'Masjid dengan TPQ dan Madin', 'Ust. Ali Akbar', 400,
         'TPQ, Parkir, Tempat Wudhu'),
        ('Musholla Ar-Rahman', 'Jl. Ki Mangunsarkoro, Tulungagung', -8.0670, 111.9040, 'Tulungagung',
         'Musholla lingkungan perumahan', '-', 100,
         'Tempat Wudhu'),
    ]
    for m in mosques:
        c.execute('''INSERT INTO mosques (name, address, lat, lon, city, description, imam_name, capacity, facilities)
                     VALUES (?,?,?,?,?,?,?,?,?)''', m)

    # Seed some events
    events = [
        (1, 'Kajian Rutin Ba\'da Maghrib', 'Kajian tafsir Al-Quran setiap Senin & Kamis', 'Pengajian', 'Setiap Senin', '18:00', 1, 'weekly'),
        (1, 'Yasin & Tahlil', 'Yasinan bersama ba\'da Isya', 'Yasinan', 'Setiap Kamis', '20:00', 1, 'weekly'),
        (2, 'Kultum Subuh', 'Ceramah singkat ba\'da Subuh', 'Kultum', 'Setiap Jumat', '05:00', 1, 'weekly'),
        (3, 'Pengajian Ibu-Ibu', 'Pengajian rutin Muslimat', 'Pengajian', 'Setiap Selasa', '09:00', 1, 'weekly'),
        (4, 'Santunan Anak Yatim', 'Bakti sosial bulanan', 'Sosial', '17 Juni 2026', '09:00', 0, None),
        (1, 'Tarhib Ramadhan', 'Persiapan menyambut bulan Ramadhan', 'Event', '15 Juni 2026', '19:30', 0, None),
    ]
    for e in events:
        c.execute('''INSERT INTO events (mosque_id, title, description, event_type, event_date, event_time, is_recurring, recurrence)
                     VALUES (?,?,?,?,?,?,?,?)''', e)

    # Seed some reviews
    reviews = [
        (1, 'Budi S.', 5, 'Masjid terbesar di Tulungagung, fasilitas lengkap dan bersih.'),
        (1, 'Ahmad K.', 4, 'Parkir luas, AC dingin. Kadang ramai saat Jumat.'),
        (2, 'Dewi R.', 4, 'Masjid nyaman, lingkungan tenang untuk beribadah.'),
        (3, 'Rizal M.', 5, 'Masjid bersejarah, arsitektur indah. Imam bacaan bagus.'),
        (4, 'Siti A.', 4, 'Dekat pasar, mudah dijangkau. Kegiatan sosial aktif.'),
    ]
    for r in reviews:
        c.execute('''INSERT INTO reviews (mosque_id, user_name, rating, comment) VALUES (?,?,?,?)''', r)

# ─── ROUTES ────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dkm')
def dkm_dashboard():
    return render_template('dkm.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ─── API: MOSQUES ──────────────────────────────────────

@app.route('/api/mosques')
def api_mosques():
    lat = float(request.args.get('lat', -8.0657))
    lon = float(request.args.get('lon', 111.9035))
    radius = int(request.args.get('radius', 5000))

    conn = get_db()
    mosques = conn.execute('SELECT * FROM mosques').fetchall()
    conn.close()

    result = []
    for m in mosques:
        d = get_distance(lat, lon, m['lat'], m['lon'])
        if d <= radius:
            # Get average rating
            conn2 = get_db()
            avg = conn2.execute('SELECT AVG(rating), COUNT(*) FROM reviews WHERE mosque_id=?', (m['id'],)).fetchone()
            conn2.close()
            result.append({
                'id': m['id'],
                'name': m['name'],
                'address': m['address'],
                'lat': m['lat'],
                'lon': m['lon'],
                'city': m['city'],
                'phone': m['phone'],
                'description': m['description'],
                'imam_name': m['imam_name'],
                'capacity': m['capacity'],
                'facilities': m['facilities'],
                'photo_url': m['photo_url'],
                'distance': d,
                'avg_rating': round(avg[0], 1) if avg[0] else 0,
                'review_count': avg[1]
            })

    result.sort(key=lambda x: x['distance'])
    return jsonify(result)

@app.route('/api/mosques/<int:mosque_id>')
def api_mosque_detail(mosque_id):
    conn = get_db()
    m = conn.execute('SELECT * FROM mosques WHERE id=?', (mosque_id,)).fetchone()
    if not m:
        return jsonify({'error': 'Not found'}), 404

    reviews = conn.execute('SELECT * FROM reviews WHERE mosque_id=? ORDER BY created_at DESC', (mosque_id,)).fetchall()
    events = conn.execute('SELECT * FROM events WHERE mosque_id=? ORDER BY event_date', (mosque_id,)).fetchall()
    avg = conn.execute('SELECT AVG(rating), COUNT(*) FROM reviews WHERE mosque_id=?', (mosque_id,)).fetchone()
    conn.close()

    return jsonify({
        'id': m['id'],
        'name': m['name'],
        'address': m['address'],
        'lat': m['lat'],
        'lon': m['lon'],
        'city': m['city'],
        'phone': m['phone'],
        'description': m['description'],
        'imam_name': m['imam_name'],
        'capacity': m['capacity'],
        'facilities': m['facilities'],
        'avg_rating': round(avg[0], 1) if avg[0] else 0,
        'review_count': avg[1],
        'reviews': [{'user_name': r['user_name'], 'rating': r['rating'], 'comment': r['comment'], 'created_at': r['created_at']} for r in reviews],
        'events': [{'id': e['id'], 'title': e['title'], 'description': e['description'], 'event_type': e['event_type'], 'event_date': e['event_date'], 'event_time': e['event_time'], 'is_recurring': e['is_recurring']} for e in events]
    })

# ─── API: EVENTS ───────────────────────────────────────

@app.route('/api/events')
def api_events():
    lat = float(request.args.get('lat', -8.0657))
    lon = float(request.args.get('lon', 111.9035))

    conn = get_db()
    events = conn.execute('''
        SELECT e.*, m.name as mosque_name, m.lat as mlat, m.lon as mlon
        FROM events e JOIN mosques m ON e.mosque_id = m.id
        ORDER BY e.event_date
    ''').fetchall()
    conn.close()

    result = []
    for e in events:
        d = get_distance(lat, lon, e['mlat'], e['mlon'])
        result.append({
            'id': e['id'],
            'mosque_id': e['mosque_id'],
            'mosque_name': e['mosque_name'],
            'title': e['title'],
            'description': e['description'],
            'event_type': e['event_type'],
            'event_date': e['event_date'],
            'event_time': e['event_time'],
            'is_recurring': e['is_recurring'],
            'distance': d
        })
    return jsonify(result)

# ─── API: REVIEWS ──────────────────────────────────────

@app.route('/api/reviews', methods=['POST'])
def api_add_review():
    data = request.json
    if not data or not data.get('mosque_id') or not data.get('rating'):
        return jsonify({'error': 'Missing fields'}), 400

    conn = get_db()
    conn.execute('''INSERT INTO reviews (mosque_id, user_name, rating, comment)
                    VALUES (?,?,?,?)''',
                 (data['mosque_id'], data.get('user_name', 'Anonim'), data['rating'], data.get('comment', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ─── API: DONATIONS ────────────────────────────────────

@app.route('/api/donations', methods=['POST'])
def api_donation():
    data = request.json
    if not data or not data.get('mosque_id') or not data.get('amount'):
        return jsonify({'error': 'Missing fields'}), 400

    conn = get_db()
    conn.execute('''INSERT INTO donations (mosque_id, donor_name, amount, message, payment_method)
                    VALUES (?,?,?,?,?)''',
                 (data['mosque_id'], data.get('donor_name', 'Hamba Allah'), data['amount'],
                  data.get('message', ''), data.get('payment_method', 'transfer')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Terima kasih atas donasi Anda. Jazakallahu khairan.'})

# ─── API: DKM ──────────────────────────────────────────

@app.route('/api/dkm/register', methods=['POST'])
def dkm_register():
    data = request.json
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing fields'}), 400

    pw_hash = hashlib.sha256(data['password'].encode()).hexdigest()
    conn = get_db()
    try:
        conn.execute('''INSERT INTO dkm_users (username, password, name, phone)
                        VALUES (?,?,?,?)''',
                     (data['username'], pw_hash, data.get('name', ''), data.get('phone', '')))
        conn.commit()
        user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        return jsonify({'success': True, 'user_id': user_id})
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Username sudah dipakai'}), 400

@app.route('/api/dkm/login', methods=['POST'])
def dkm_login():
    data = request.json
    pw_hash = hashlib.sha256(data['password'].encode()).hexdigest()
    conn = get_db()
    user = conn.execute('SELECT * FROM dkm_users WHERE username=? AND password=?',
                        (data['username'], pw_hash)).fetchone()
    conn.close()

    if user:
        session['dkm_user_id'] = user['id']
        session['dkm_mosque_id'] = user['mosque_id']
        return jsonify({'success': True, 'user_id': user['id'], 'mosque_id': user['mosque_id'], 'name': user['name']})
    return jsonify({'error': 'Username atau password salah'}), 401

@app.route('/api/dkm/add-mosque', methods=['POST'])
def dkm_add_mosque():
    data = request.json
    conn = get_db()
    conn.execute('''INSERT INTO mosques (name, address, lat, lon, city, phone, description, imam_name, capacity, facilities)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''',
                 (data['name'], data.get('address', ''), data.get('lat', 0), data.get('lon', 0),
                  data.get('city', ''), data.get('phone', ''), data.get('description', ''),
                  data.get('imam_name', ''), data.get('capacity', 0), data.get('facilities', '')))
    conn.commit()
    mosque_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    return jsonify({'success': True, 'mosque_id': mosque_id})

@app.route('/api/dkm/add-event', methods=['POST'])
def dkm_add_event():
    data = request.json
    conn = get_db()
    conn.execute('''INSERT INTO events (mosque_id, title, description, event_type, event_date, event_time, is_recurring, recurrence)
                    VALUES (?,?,?,?,?,?,?,?)''',
                 (data['mosque_id'], data['title'], data.get('description', ''),
                  data.get('event_type', 'Lainnya'), data.get('event_date', ''),
                  data.get('event_time', ''), data.get('is_recurring', 0), data.get('recurrence', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/dkm/mosque/<int:mosque_id>/events')
def dkm_mosque_events(mosque_id):
    conn = get_db()
    events = conn.execute('SELECT * FROM events WHERE mosque_id=? ORDER BY event_date DESC', (mosque_id,)).fetchall()
    conn.close()
    return jsonify([dict(e) for e in events])

@app.route('/api/dkm/mosque/<int:mosque_id>/donations')
def dkm_mosque_donations(mosque_id):
    conn = get_db()
    donations = conn.execute('SELECT * FROM donations WHERE mosque_id=? ORDER BY created_at DESC', (mosque_id,)).fetchall()
    total = conn.execute('SELECT SUM(amount) FROM donations WHERE mosque_id=? AND status="confirmed"', (mosque_id,)).fetchone()
    conn.close()
    return jsonify({
        'donations': [dict(d) for d in donations],
        'total': total[0] or 0
    })

# ─── API: SUGGEST MOSQUE ──────────────────────────────

@app.route('/api/suggest-mosque', methods=['POST'])
def api_suggest_mosque():
    data = request.json
    if not data or not data.get('name') or not data.get('lat') or not data.get('lon'):
        return jsonify({'error': 'Nama masjid dan lokasi wajib diisi'}), 400

    conn = get_db()
    conn.execute('''INSERT INTO suggest_mosques (name, address, lat, lon, city, suggester_name, suggester_phone, notes)
                    VALUES (?,?,?,?,?,?,?,?)''',
                 (data['name'], data.get('address', ''), data['lat'], data['lon'],
                  data.get('city', ''), data.get('suggester_name', ''), data.get('suggester_phone', ''),
                  data.get('notes', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Terima kasih! Masjid akan diverifikasi oleh tim kami.'})

@app.route('/api/suggest-event', methods=['POST'])
def api_suggest_event():
    data = request.json
    if not data or not data.get('title'):
        return jsonify({'error': 'Judul kegiatan wajib diisi'}), 400

    conn = get_db()
    conn.execute('''INSERT INTO suggest_events (mosque_id, mosque_name, title, description, event_type, event_date, event_time, suggester_name)
                    VALUES (?,?,?,?,?,?,?,?)''',
                 (data.get('mosque_id'), data.get('mosque_name', ''),
                  data['title'], data.get('description', ''),
                  data.get('event_type', 'Lainnya'), data.get('event_date', ''),
                  data.get('event_time', ''), data.get('suggester_name', '')))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Terima kasih! Kegiatan akan diverifikasi oleh DKM.'})

# ─── API: OSM MOSQUES PROXY ───────────────────────────

import urllib.request
import urllib.parse

@app.route('/api/osm-mosques')
def api_osm_mosques():
    lat = float(request.args.get('lat', -8.0657))
    lon = float(request.args.get('lon', 111.9035))
    radius = int(request.args.get('radius', 5000))

    query = f"""[out:json][timeout:10];
        (
            node["amenity"="place_of_worship"]["religion"="muslim"](around:{radius},{lat},{lon});
            way["amenity"="place_of_worship"]["religion"="muslim"](around:{radius},{lat},{lon});
        );
        out center 30;"""

    try:
        url = 'https://overpass-api.de/api/interpreter'
        data = urllib.parse.urlencode({'data': query}).encode()
        req = urllib.request.Request(url, data=data, headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'SholatKuApp/1.0 (https://sholatku.qzz.io)'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            osm_data = json.loads(resp.read().decode())

        result = []
        for el in osm_data.get('elements', []):
            elat = el.get('lat') or (el.get('center', {}) or {}).get('lat')
            elon = el.get('lon') or (el.get('center', {}) or {}).get('lon')
            if not elat or not elon:
                continue
            d = get_distance(lat, lon, elat, elon)
            tags = el.get('tags', {})
            result.append({
                'id': f'osm_{el["id"]}',
                'name': tags.get('name', 'Masjid'),
                'address': tags.get('addr:street', tags.get('addr:full', '')),
                'lat': elat,
                'lon': elon,
                'city': tags.get('addr:city', ''),
                'phone': tags.get('phone', tags.get('contact:phone', '')),
                'description': '',
                'imam_name': '',
                'capacity': 0,
                'facilities': '',
                'distance': d,
                'avg_rating': 0,
                'review_count': 0,
                'source': 'osm'
            })

        result.sort(key=lambda x: x['distance'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'result': []}), 500

def get_distance(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return round(R * 2 * atan2(sqrt(a), sqrt(1-a)))

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5050, debug=False)
