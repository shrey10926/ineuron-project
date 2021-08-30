from flask import Flask, render_template, request
import pandas as pd
import numpy as np
import pickle

app = Flask(__name__)

model = pickle.load(open('model.pkl', 'rb'))

@app.route('/')
def man():
    return render_template('home.html')


@app.route('/predict', methods = ['POST'])
def home():
    compact = request.form['compactness']
    k_length = request.form['kernel_length']
    Width = request.form['width']
    asymm_coef = request.form['asymmetry_coef']
    g_length = request.form['groove_length']
    
    arr = np.array([[compact, k_length, Width, asymm_coef, g_length]])
    
    arr1 = pd.DataFrame(arr, columns = ['compactness', 'kernel_length', 
                                        'width', 'asymmetry_coef', 'groove_length'])
    
    pred = model.predict(arr1)
    
    return render_template('after.html', data = pred)

if __name__ == '__main__':
    app.run(debug = True)

    












