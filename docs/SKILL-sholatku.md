---
name: sholatku-app-management
description: Manage SholatKu app — mosques, events, DKM users, reviews, donations. Flask + SQLite on port 5050, Cloudflare Tunnel to sholatku.qzz.io.
triggers:
  - sholatku
  - sholat app
  - masjid
  - mosque
  - dkm
  - event masjid
  - sholatku.qzz.io
  - jadwal sholat
  - donasi masjid
---

# SholatKu App Management

## Overview
Flask + SQLite app for mosque finder & prayer times.
URL: `https://sholatku.qzz.io` (via Cloudflare Tunnel)
Source: `~/sholat-app/app.py`
GitHub: `Pujagaul6/sholatku-app`
Systemd services: `sholatku-app` (port 5050), `sholatku-tunnel` (Cloudflare)

## File Structure
```
~/sholat-app/
├── app.py              # Flask app (all routes + API)
├── sholatku.db         # SQLite database
├── templates/
│   ├── index.html      # Main PWA page
│   └── dkm.html        # DKM dashboard
├── static/
│   ├── sw.js           # Service worker
│   ├── manifest.json   # PWA manifest
│   ├── icon-192.png    # PWA icon
│   ├── icon-512.png    # PWA icon
│   ├── offline.html    # Offline fallback
│   └── js/             # JavaScript files
└── db-backup/          # GitHub-tracked DB backups
```

## Database Schema

### mosques
- id, name, address, lat (REAL), lon (REAL), city, phone, description
- imam_name, capacity (INTEGER), facilities (TEXT), photo_url
- dkm_user_id, verified (INTEGER), created_at

### dkm_users
- id, username, password, mosque_id, name, phone, created_at

### events
- id, mosque_id, title, description, event_type
- event_date, event_time, is_recurring (INTEGER), recurrence, created_at

### reviews
- id, mosque_id, user_name, rating (INTEGER), comment, created_at

### donations
- id, mosque_id, donor_name, amount (REAL), message, payment_method, status, created_at

### suggest_mosques
- id, name, address, lat, lon, city, suggester_name, suggester_phone, notes, status, created_at

### suggest_events
- id, mosque_id, mosque_name, title, description, event_type, event_date, event_time, suggester_name, status, created_at

## API Endpoints
- `GET /api/mosques?lat=&lon=` — nearby mosques (Haversine distance)
- `GET /api/mosques/<id>` — mosque detail
- `GET /api/events?lat=&lon=` — nearby events
- `POST /api/reviews` — add review {mosque_id, user_name, rating, comment}
- `POST /api/donations` — add donation {mosque_id, donor_name, amount, message}
- `POST /api/dkm/register` — register DKM user
- `POST /api/dkm/login` — DKM login
- `POST /api/dkm/add-mosque` — DKM add mosque
- `POST /api/dkm/add-event` — DKM add event
- `POST /api/suggest-mosque` — user suggests mosque
- `POST /api/suggest-event` — user suggests event
- `GET /api/osm-mosques?lat=&lon=&radius=` — OpenStreetMap fallback

## Operations

### Add Mosque
```bash
cd ~/sholat-app
python3 -c "
import sqlite3
conn = sqlite3.connect('sholatku.db')
conn.execute('''INSERT INTO mosques 
    (name, address, lat, lon, city, phone, description, imam_name, capacity, facilities, verified)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)''',
    ('Masjid Al-Ikhlas', 'Jl. Raya Tulungagung No. 1', -8.0657, 111.9035, 
     'Tulungagung', '08123456789', 'Masjid besar di pusat kota', 
     'Ustadz Ahmad', 500, 'AC, Sound System, Parkir Luas'))
conn.commit(); print('Added'); conn.close()
"
```

### Edit Mosque
```bash
cd ~/sholat-app
python3 -c "
import sqlite3
conn = sqlite3.connect('sholatku.db')
conn.execute('UPDATE mosques SET name=?, description=?, phone=? WHERE id=?',
    ('Nama Baru', 'Deskripsi baru', '08123456789', 1))
conn.commit(); print('Updated'); conn.close()
"
```

### Add Event
```bash
cd ~/sholat-app
python3 -c "
import sqlite3
conn = sqlite3.connect('sholatku.db')
conn.execute('''INSERT INTO events 
    (mosque_id, title, description, event_type, event_date, event_time, is_recurring)
    VALUES (?, ?, ?, ?, ?, ?, ?)''',
    (1, 'Kajian Rutin Ahad', 'Kajian ba\'da subuh setiap Ahad', 'kajian',
     '2026-06-22', '05:30', 0))
conn.commit(); print('Added'); conn.close()
"
```

### List All Mosques
```bash
cd ~/sholat-app && python3 -c "
import sqlite3
conn = sqlite3.connect('sholatku.db')
for r in conn.execute('SELECT id, name, city, lat, lon, verified FROM mosques ORDER BY name').fetchall():
    v = '✅' if r[5] else '❌'
    print(f'ID:{r[0]} | {r[1]} | {r[2]} | ({r[3]},{r[4]}) | {v}')
conn.close()
"
```

### List Events
```bash
cd ~/sholat-app && python3 -c "
import sqlite3
conn = sqlite3.connect('sholatku.db')
for r in conn.execute('SELECT e.id, m.name, e.title, e.event_date, e.event_time FROM events e LEFT JOIN mosques m ON e.mosque_id=m.id ORDER BY e.event_date DESC LIMIT 20').fetchall():
    print(f'#{r[0]} | {r[1]} | {r[2]} | {r[3]} {r[4]}')
conn.close()
"
```

### Approve Suggested Mosque
```bash
cd ~/sholat-app
python3 -c "
import sqlite3
conn = sqlite3.connect('sholatku.db')
# Get suggestion
s = conn.execute('SELECT * FROM suggest_mosques WHERE id=?', (1,)).fetchone()
if s:
    conn.execute('''INSERT INTO mosques (name, address, lat, lon, city, verified) 
        VALUES (?,?,?,?,?,1)''', (s[1], s[2], s[3], s[4], s[5]))
    conn.execute('UPDATE suggest_mosques SET status=? WHERE id=?', ('approved', 1))
    conn.commit(); print('Approved & added')
conn.close()
"
```

### Add DKM User
```bash
cd ~/sholat-app
python3 -c "
from werkzeug.security import generate_password_hash
import sqlite3
conn = sqlite3.connect('sholatku.db')
conn.execute('INSERT INTO dkm_users (username, password, mosque_id, name, phone) VALUES (?,?,?,?,?)',
    ('dkm_alikhlas', generate_password_hash('password123'), 1, 'Pak Karim', '08123456789'))
conn.commit(); print('DKM user added'); conn.close()
"
```

### Service Management
```bash
# App
sudo systemctl status sholatku-app
sudo systemctl restart sholatku-app
journalctl -u sholatku-app -f

# Tunnel
sudo systemctl status sholatku-tunnel
sudo systemctl restart sholatku-tunnel
journalctl -u sholatku-tunnel -f
```

### Cloudflare Tunnel Config
Location: `~/.cloudflared/config-sholatku.yml`
```yaml
tunnel: <tunnel-id>
credentials-file: /home/ubuntu/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: sholatku.qzz.io
    service: http://localhost:5050
  - service: http_status:404
```

### Backup & Restore
```bash
# Manual backup
cp ~/sholat-app/sholatku.db ~/sholat-app/sholatku_backup_$(date +%Y%m%d).db

# Restore
sudo systemctl stop sholatku-app
cp ~/sholat-app/db-backup/sholatku_20260616_123758.db ~/sholat-app/sholatku.db
sudo systemctl start sholatku-app
```

## Pitfalls
- **Port 5050** — not 80 like Kasir App
- **Two systemd services** must be running: `sholatku-app` + `sholatku-tunnel`
- **Cloudflare Tunnel errors** when app restarts — connection refused is temporary
- **GPS/Location** — app uses browser Geolocation API, auto-requests on first visit
- **Prayer times** — fetched from external API (aladhan.com), not stored in DB
- **Mosque data** — seeded 6 mosques initially, more added via DKM dashboard or suggestions
- **OpenStreetMap fallback** — may have limited data in rural areas
- **Notifications** — browser-based, requires tab open + permission granted
- **Daily backup at 02:00 WIB** via cron (~/scripts/backup-to-github.sh)
- **PWA install** — users can "Add to Home Screen" on mobile
