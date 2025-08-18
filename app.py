from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# -----------------------------------
# Flask App & DB Config
# -----------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = "replace_this_with_a_random_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///techmart.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -----------------------------------
# Models
# -----------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    image_url = db.Column(db.String(255), nullable=True)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    user = db.relationship("User", backref=db.backref("cart_items", lazy="dynamic"))
    product = db.relationship("Product")


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    user = db.relationship("User", backref=db.backref("orders", lazy="dynamic"))
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    price_at_purchase = db.Column(db.Float, nullable=False)

    product = db.relationship("Product")

# -----------------------------------
# Helpers
# -----------------------------------
def current_user_id():
    return session.get("user_id")

def require_login():
    if not current_user_id():
        flash("Please login first.", "warning")
        return redirect(url_for("login"))
    return None

def seed_products():
    """Seed a few demo products once."""
    if Product.query.count() > 0:
        return
    demo = [
        {
            "name": "Lenovo IdeaPad 3",
            "price": 45990,
            "description": "15.6\" FHD, Ryzen 5, 8GB RAM, 512GB SSD",
            "image_url": "https://via.placeholder.com/400x260?text=Lenovo+IdeaPad+3",
        },
        {
            "name": "Apple iPhone 14",
            "price": 66990,
            "description": "6.1\" Super Retina XDR, 128GB",
            "image_url": "https://via.placeholder.com/400x260?text=iPhone+14",
        },
        {
            "name": "Samsung Galaxy Tab S9",
            "price": 62999,
            "description": "11\" Dynamic AMOLED, S Pen",
            "image_url": "https://via.placeholder.com/400x260?text=Galaxy+Tab+S9",
        },
        {
            "name": "Noise ColorFit Pro 4",
            "price": 2999,
            "description": "1.72\" Display, BT calling, Fitness tracking",
            "image_url": "https://via.placeholder.com/400x260?text=Noise+Smartwatch",
        },
        {
            "name": "Sony WH-CH720N",
            "price": 8990,
            "description": "ANC Wireless Headphones, 35h battery",
            "image_url": "https://via.placeholder.com/400x260?text=Sony+Headphones",
        },
    ]
    for d in demo:
        db.session.add(Product(**d))
    db.session.commit()

# -----------------------------------
# Routes: Auth
# -----------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already exists.", "danger")
            return redirect(url_for("register"))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            flash("Welcome back!", "success")
            return redirect(url_for("index"))
        flash("Invalid username or password.", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# -----------------------------------
# Routes: Catalog, Search, Cart, Orders
# -----------------------------------
@app.route("/")
def index():
    # Force login to see products
    if not current_user_id():
        return redirect(url_for("login"))

    q = (request.args.get("q") or "").strip()
    products_query = Product.query
    if q:
        like = f"%{q}%"
        products_query = products_query.filter(
            db.or_(Product.name.ilike(like), Product.description.ilike(like))
        )
    products = products_query.order_by(Product.name).all()
    return render_template("index.html", products=products, q=q)


@app.route("/cart")
def cart():
    if require_login():
        return require_login()
    items = (
        CartItem.query.filter_by(user_id=current_user_id())
        .join(Product, CartItem.product_id == Product.id)
        .all()
    )
    # compute totals
    total = sum(item.quantity * item.product.price for item in items)
    return render_template("cart.html", items=items, total=total)


@app.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    if require_login():
        return require_login()

    qty = request.form.get("quantity", "1")
    try:
        qty = max(1, int(qty))
    except ValueError:
        qty = 1

    item = CartItem.query.filter_by(
        user_id=current_user_id(), product_id=product_id
    ).first()

    if item:
        item.quantity += qty
    else:
        item = CartItem(user_id=current_user_id(), product_id=product_id, quantity=qty)
        db.session.add(item)
    db.session.commit()
    flash("Added to cart.", "success")
    return redirect(url_for("index"))


@app.route("/cart/update", methods=["POST"])
def cart_update():
    if require_login():
        return require_login()

    # Expect form fields like quantity_<item_id>
    for key, value in request.form.items():
        if key.startswith("quantity_"):
            try:
                item_id = int(key.split("_", 1)[1])
                qty = max(0, int(value))
                item = CartItem.query.filter_by(
                    id=item_id, user_id=current_user_id()
                ).first()
                if item:
                    if qty == 0:
                        db.session.delete(item)
                    else:
                        item.quantity = qty
            except ValueError:
                continue
    db.session.commit()
    flash("Cart updated.", "success")
    return redirect(url_for("cart"))


@app.route("/checkout", methods=["POST"])
def checkout():
    if require_login():
        return require_login()

    cart_items = CartItem.query.filter_by(user_id=current_user_id()).all()
    if not cart_items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("cart"))

    order = Order(user_id=current_user_id())
    db.session.add(order)
    db.session.flush()  # get order.id

    for ci in cart_items:
        db.session.add(
            OrderItem(
                order_id=order.id,
                product_id=ci.product_id,
                quantity=ci.quantity,
                price_at_purchase=ci.product.price,
            )
        )
        db.session.delete(ci)

    db.session.commit()
    flash("Order placed successfully!", "success")
    return redirect(url_for("orders"))


@app.route("/orders")
def orders():
    if require_login():
        return require_login()

    user_orders = (
        Order.query.filter_by(user_id=current_user_id())
        .order_by(Order.created_at.desc())
        .all()
    )
    return render_template("orders.html", orders=user_orders)

# -----------------------------------
# App bootstrap (create tables & seed on first run)
# -----------------------------------
with app.app_context():
    db.create_all()
    seed_products()

# -----------------------------------
# Run
# -----------------------------------
if __name__ == "__main__":
    app.run(debug=True)
