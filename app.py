from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import requests
import joblib
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://username:password@localhost/farmer_schemes_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = 'supersecretkey'

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'user'), nullable=False)

class MarketPrice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    crop_id = db.Column(db.Integer, db.ForeignKey('crop.id'), nullable=False)
    market_location = db.Column(db.String(255), nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    recorded_date = db.Column(db.Date, nullable=False)

class Crop(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(50), default='pending')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    new_user = User(username=data['username'], password=hashed_password, role='user')
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if user and bcrypt.check_password_hash(user.password, data['password']):
        access_token = create_access_token(identity={'username': user.username, 'role': user.role})
        return jsonify(access_token=access_token), 200
    return jsonify({'message': 'Invalid credentials'}), 401

@app.route('/admin/approve-application', methods=['POST'])
@jwt_required()
def approve_application():
    current_user = get_jwt_identity()
    if current_user['role'] != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
    data = request.get_json()
    application = Application.query.get(data['application_id'])
    if application:
        application.status = 'approved'
        db.session.commit()
        return jsonify({'message': 'Application approved successfully'})
    return jsonify({'message': 'Application not found'}), 404

@app.route('/weather', methods=['GET'])
def get_weather():
    city = request.args.get('city', 'Delhi')
    api_key = "your_openweather_api_key"
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)
    if response.status_code == 200:
        weather_data = response.json()
        return jsonify({
            'temperature': weather_data['main']['temp'],
            'humidity': weather_data['main']['humidity'],
            'forecast': weather_data['weather'][0]['description']
        })
    return jsonify({'message': 'Error fetching weather data'}), 500

@app.route('/recommend-crops', methods=['GET'])
def recommend_crops():
    temperature = request.args.get('temperature', type=float, default=25.0)
    humidity = request.args.get('humidity', type=float, default=60.0)
    model = joblib.load('crop_recommendation_model.pkl')
    recommended_crop = model.predict([[temperature, humidity]])[0]
    return jsonify({'recommended_crop': recommended_crop})

@app.route('/market-prices', methods=['GET'])
def get_market_prices():
    today = datetime.date.today()
    prices = MarketPrice.query.filter_by(recorded_date=today).all()
    price_list = [{'crop_id': p.crop_id, 'market_location': p.market_location, 'price': p.price_per_unit, 'unit': p.unit} for p in prices]
    return jsonify(price_list)

if __name__ == '__main__':
    app.run(debug=True)
