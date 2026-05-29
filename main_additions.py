# ══════════════════════════════════════════════════════════════
# CHANGES NEEDED IN main.py
# Apply these one section at a time.
# ══════════════════════════════════════════════════════════════

# ── 1. ADD to Seller model (inside the class) ──────────────────
#    Add these 4 new columns after selected_template:

#    whatsapp   = db.Column(db.String(20))
#    latitude   = db.Column(db.String(20))
#    longitude  = db.Column(db.String(20))
#    maps_link  = db.Column(db.Text)

# So your Seller model becomes:
class Seller(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    shop_name         = db.Column(db.String(200), nullable=False)
    selected_marbles  = db.Column(db.String(1000))
    address           = db.Column(db.Text)
    description       = db.Column(db.Text)
    shop_photos       = db.Column(db.Text)
    selected_template = db.Column(db.String(50), default='template1')
    whatsapp          = db.Column(db.String(20))   # NEW
    latitude          = db.Column(db.String(20))   # NEW
    longitude         = db.Column(db.String(20))   # NEW
    maps_link         = db.Column(db.Text)         # NEW


# ── 2. UPDATE /info POST route ─────────────────────────────────
#    In the existing /info POST handler, add these lines
#    where you collect form data:

@app.route('/info', methods=['GET', 'POST'])
def info():
    if 'username' not in session:
        return redirect('/register')

    user = User.query.filter_by(username=session['username']).first()
    if not user:
        return redirect('/register')

    if request.method == 'GET':
        existing_seller = Seller.query.filter_by(user_id=user.id).first()
        if existing_seller:
            return redirect('/dashboard')
        marbles = Marble.query.all()
        return render_template('info.html', user=user, marbles=marbles)

    if request.method == 'POST':
        shop_name        = request.form.get('shopn')
        address          = request.form.get('address')
        description      = request.form.get('description')
        selected_marbles = request.form.getlist('selected_marbles')
        whatsapp         = request.form.get('whatsapp', '')   # NEW
        latitude         = request.form.get('latitude', '')   # NEW
        longitude        = request.form.get('longitude', '')  # NEW
        maps_link        = request.form.get('maps_link', '')  # NEW

        # Handle shop photos
        shop_photos_list = request.files.getlist('shop_photos')
        saved_filenames  = []
        for photo in shop_photos_list:
            if photo and photo.filename:
                filename = f"shop_{user.id}_{secure_filename(photo.filename)}"
                photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                saved_filenames.append(filename)

        # Save to session for selecttemp step
        session['shop_info'] = {
            'shop_name':        shop_name,
            'address':          address,
            'description':      description,
            'selected_marbles': ','.join(selected_marbles),
            'shop_photos':      ','.join(saved_filenames),
            'whatsapp':         whatsapp,   # NEW
            'latitude':         latitude,   # NEW
            'longitude':        longitude,  # NEW
            'maps_link':        maps_link,  # NEW
        }
        return redirect('/selecttemp')


# ── 3. UPDATE /selecttemp POST route ──────────────────────────
#    When creating the Seller object, include new fields:

new_seller = Seller(
    user_id          = user.id,
    shop_name        = shop_info['shop_name'],
    address          = shop_info.get('address', ''),
    description      = shop_info.get('description', ''),
    selected_marbles = shop_info.get('selected_marbles', ''),
    shop_photos      = shop_info.get('shop_photos', ''),
    selected_template= selected_template,
    whatsapp         = shop_info.get('whatsapp', ''),   # NEW
    latitude         = shop_info.get('latitude', ''),   # NEW
    longitude        = shop_info.get('longitude', ''),  # NEW
    maps_link        = shop_info.get('maps_link', ''),  # NEW
)


# ── 4. UPDATE /dashboard/edit/info POST route ─────────────────
#    Add the new fields to the edit handler too:

@app.route('/dashboard/edit/info', methods=['GET', 'POST'])
def edit_info():
    if 'username' not in session:
        return redirect('/login')

    user   = User.query.filter_by(username=session['username']).first()
    seller = Seller.query.filter_by(user_id=user.id).first()
    if not seller:
        return redirect('/info')

    if request.method == 'GET':
        return render_template('edit_info.html', seller=seller)

    if request.method == 'POST':
        seller.shop_name   = request.form.get('shop_name')
        seller.address     = request.form.get('address')
        seller.description = request.form.get('description')
        seller.whatsapp    = request.form.get('whatsapp', '')   # NEW
        seller.latitude    = request.form.get('latitude', '')   # NEW
        seller.longitude   = request.form.get('longitude', '')  # NEW
        seller.maps_link   = request.form.get('maps_link', '')  # NEW
        db.session.commit()

        flash('Shop info updated!')
        return redirect('/dashboard')


# ── 5. RUN THIS migration script once ─────────────────────────
#    Create migrate2.py and run: python migrate2.py

from main import app, db

with app.app_context():
    db.session.execute(db.text('ALTER TABLE seller ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(20)'))
    db.session.execute(db.text('ALTER TABLE seller ADD COLUMN IF NOT EXISTS latitude VARCHAR(20)'))
    db.session.execute(db.text('ALTER TABLE seller ADD COLUMN IF NOT EXISTS longitude VARCHAR(20)'))
    db.session.execute(db.text('ALTER TABLE seller ADD COLUMN IF NOT EXISTS maps_link TEXT'))
    db.session.commit()
    print("Done! 4 new columns added to seller table.")
