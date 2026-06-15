"""
Flask web app with multiple pages: Home, Features, Working, Privacy
"""
from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    """Home page"""
    return render_template('home.html')

@app.route('/features')
def features():
    """Features page"""
    return render_template('features.html')

@app.route('/working')
def working():
    """How it works page"""
    return render_template('working.html')

@app.route('/privacy')
def privacy():
    """Privacy policy page"""
    return render_template('privacy.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
