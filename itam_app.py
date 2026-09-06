from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'dev-secret-key-change-this'  # replace before any real deployment

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'assets.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')

FORM_SECTIONS = [
    ('Device Info', [
        ('serial', 'Serial', True),
        ('tag_number', 'Tag Number', False),
        ('model', 'Model', False),
        ('mac', 'MAC Address', False),
    ]),
    ('Peripherals', [
        ('keyboard', 'Keyboard', False),
        ('mouse', 'Mouse', False),
        ('monitor_left', 'Monitor 1 (Left)', False),
        ('monitor_right', 'Monitor 2 (Right)', False),
        ('power_adapter', 'Power Adapter', False),
        ('vga', 'VGA', False),
        ('headset', 'Headset', False),
    ]),
    ('Assignment', [
        ('user', 'User', False),
        ('location', 'Location', False),
        ('sub_location', 'Sub Location', False),
        ('area', 'Area', False),
        ('sub_area', 'Sub Area', False),
        ('site', 'Site', False),
    ]),
    ('Procurement', [
        ('po_number', 'PO Number', False),
        ('qeid', 'QEID', False),
        ('pein', 'PEIN', False),
        ('image', 'Image', False),
        ('hpdm_hostname', 'HPDM Hostname', False),
    ]),
    ('Lifecycle', [
        ('date_deployed', 'Date Deployed', False),
        ('date_returned', 'Date Returned', False),
        ('warranty_start', 'Warranty Start', False),
        ('warranty_end', 'Warranty End', False),
        ('status', 'Status', False),
    ]),
]

STATUS_OPTIONS = ['Deployed', 'In Repair', 'Storage', 'Retired']

ALL_FIELDS = [f[0] for _, fields in FORM_SECTIONS for f in fields]


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


@app.route('/')
def index():
    return redirect(url_for('list_assets'))


@app.route('/assets')
def list_assets():
    conn = get_db_connection()
    query = "SELECT * FROM assets"
    filters = []
    params = []

    status_filter = request.args.get('status')
    site_filter = request.args.get('site')
    search = request.args.get('search')

    if status_filter and status_filter != 'All':
        filters.append("status = ?")
        params.append(status_filter)

    if site_filter and site_filter != 'All':
        filters.append("site = ?")
        params.append(site_filter)

    if search:
        filters.append("(serial LIKE ? OR user LIKE ? OR hpdm_hostname LIKE ? OR tag_number LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like, like])

    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY date_added DESC"

    assets = conn.execute(query, params).fetchall()

    total = conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
    deployed = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Deployed'").fetchone()[0]
    in_repair = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'In Repair'").fetchone()[0]
    retired = conn.execute("SELECT COUNT(*) FROM assets WHERE status = 'Retired'").fetchone()[0]

    sites = [r['site'] for r in conn.execute(
        "SELECT DISTINCT site FROM assets WHERE site != '' ORDER BY site"
    ).fetchall()]

    conn.close()

    return render_template(
        'assets.html',
        assets=assets,
        total=total,
        deployed=deployed,
        in_repair=in_repair,
        retired=retired,
        current_status=status_filter or 'All',
        current_site=site_filter or 'All',
        sites=sites,
        status_options=STATUS_OPTIONS,
        search=search or ''
    )


@app.route('/assets/<int:asset_id>')
def view_asset(asset_id):
    conn = get_db_connection()
    asset = conn.execute('SELECT * FROM assets WHERE id = ?', (asset_id,)).fetchone()
    conn.close()

    if asset is None:
        flash('Asset not found.', 'error')
        return redirect(url_for('list_assets'))

    return render_template('asset_detail.html', asset=asset, sections=FORM_SECTIONS)


@app.route('/assets/add', methods=['GET', 'POST'])
def add_asset():
    if request.method == 'POST':
        values = {field: request.form.get(field, '').strip() for field in ALL_FIELDS}

        if not values['status']:
            values['status'] = 'Deployed'

        conn = get_db_connection()
        try:
            columns = ', '.join(values.keys())
            placeholders = ', '.join('?' for _ in values)
            conn.execute(
                f"INSERT INTO assets ({columns}) VALUES ({placeholders})",
                list(values.values())
            )
            conn.commit()
            flash(f"Asset '{values['serial']}' added successfully.", 'success')
            return redirect(url_for('list_assets'))
        except sqlite3.IntegrityError:
            flash('That serial number already exists.', 'error')
        finally:
            conn.close()

        return render_template('asset_form.html', asset=values, sections=FORM_SECTIONS, status_options=STATUS_OPTIONS)

    return render_template('asset_form.html', asset=None, sections=FORM_SECTIONS, status_options=STATUS_OPTIONS)


@app.route('/assets/<int:asset_id>/edit', methods=['GET', 'POST'])
def edit_asset(asset_id):
    conn = get_db_connection()

    if request.method == 'POST':
        values = {field: request.form.get(field, '').strip() for field in ALL_FIELDS}

        try:
            set_clause = ', '.join(f"{field} = ?" for field in ALL_FIELDS)
            conn.execute(
                f"UPDATE assets SET {set_clause} WHERE id = ?",
                list(values.values()) + [asset_id]
            )
            conn.commit()
            flash('Asset updated.', 'success')
            conn.close()
            return redirect(url_for('view_asset', asset_id=asset_id))
        except sqlite3.IntegrityError:
            flash('That serial number is already in use by another asset.', 'error')
            conn.close()
            values['id'] = asset_id
            return render_template('asset_form.html', asset=values, sections=FORM_SECTIONS, status_options=STATUS_OPTIONS)

    asset = conn.execute('SELECT * FROM assets WHERE id = ?', (asset_id,)).fetchone()
    conn.close()

    if asset is None:
        flash('Asset not found.', 'error')
        return redirect(url_for('list_assets'))

    return render_template('asset_form.html', asset=asset, sections=FORM_SECTIONS, status_options=STATUS_OPTIONS)


@app.route('/assets/<int:asset_id>/delete', methods=['POST'])
def delete_asset(asset_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM assets WHERE id = ?', (asset_id,))
    conn.commit()
    conn.close()
    flash('Asset deleted.', 'success')
    return redirect(url_for('list_assets'))


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5050, use_reloader=False)