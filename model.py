
# Importing all the necessary libraries
import os

import optuna

import pickle

import pandas as pd

import numpy as np

import matplotlib.pyplot as plt

import sklearn

import seaborn as sns

from sklearn.model_selection import (train_test_split, cross_val_score, 
                                    learning_curve)

from sklearn.neighbors import KNeighborsClassifier, LocalOutlierFactor

from sklearn.ensemble import RandomForestClassifier

from sklearn.tree import DecisionTreeClassifier

from xgboost import XGBClassifier

from sklearn.pipeline import Pipeline

from sklearn.impute import SimpleImputer

from sklearn.compose import ColumnTransformer

from sklearn.metrics import (mean_squared_error, classification_report, 
                             confusion_matrix, f1_score)

from sklearn.preprocessing import MinMaxScaler, StandardScaler, OneHotEncoder

from sklearn.metrics import (make_scorer, accuracy_score, precision_score, 
                             recall_score, f1_score)

os.chdir('D:\Shrey\iNeuron\Wheat Data Classification\Data Set')

# Importing the data 
data = pd.read_excel('train.xlsx')
data

# Creating a copy of the data
data1 = data.copy(deep = True)
data1

# Dropping the duplicate values
data1.drop_duplicates(keep = 'first', inplace = True)

r_list = ['area', 'perimeter']
data2 = data1.drop(r_list, axis = 1)

data2.rename(columns = {'kernel length' : 'kernel_length', 'asymmetry coef' : 'asymmetry_coef',
                                'groove length' : 'groove_length'}, inplace = True)


# Separating input and output variables
y = data2['variety']
data2.drop(['variety'], axis = 1, inplace = True)

# Separating categorical and numerical variables
num_cols = [cname for cname in data2.columns if data2[cname].dtype in ['int64', 
                                                                       'float64']]
cat_cols = [cname for cname in data2.columns if data2[cname].dtype == 'object']

# Defining preprocessing steps and bunching them into a Pipeline
num_trans = SimpleImputer(strategy = 'mean')
cat_trans = Pipeline(steps = [('impute', SimpleImputer(strategy = 'most_frequent')), 
                              ('encode', OneHotEncoder(handle_unknown = 'ignore'))])

preproc = ColumnTransformer(transformers = [('cat', cat_trans, cat_cols), 
                                            ('num', num_trans, num_cols)])

# Defining model instance
model = KNeighborsClassifier()

# Final Pipeline which performs preprocessing steps and fits the model
pipe = Pipeline(steps = [('preproc', preproc), ('model', model)])

# Splitting the data into train and test sets with test size = 20%
train_x, test_x, train_y, test_y = train_test_split(data2, y, test_size = 0.2, 
                                                    random_state = 69, stratify = y)

# Creating separate copies of train and test sets to apply scaling
train_x2 = train_x.copy(deep = True)
test_x2 = test_x.copy(deep = True)

s_scaler = StandardScaler()
s_scaler.fit(train_x2)
s_scaled_train = s_scaler.transform(train_x2)
s_scaled_test = s_scaler.transform(test_x2)

# Removing outliers
lof = LocalOutlierFactor()

yhat = lof.fit_predict(train_x2)
mask = yhat != -1
train_x2, train_y = train_x2[mask], train_y[mask]

yhat1 = lof.fit_predict(test_x2)
mask1 = yhat1 != -1
test_x2, test_y = test_x2[mask1], test_y[mask1]



# Hyperparameter tuning using Optuna
def objective(trial):
    
    
    model__n_neighbors = trial.suggest_int('model__n_neighbors', 1, 20)
    model__metric = trial.suggest_categorical('model__metric', ['euclidean', 'manhattan', 
                                                                'minkowski'])
    model__weights = trial.suggest_categorical('model__weights', ['uniform', 'distance'])
    
    params = {'model__n_neighbors' : model__n_neighbors, 
              'model__metric' : model__metric, 
              'model__weights' : model__weights}
    
    pipe.set_params(**params)
    
    return np.mean(cross_val_score(pipe, train_x2, train_y, cv = 5, 
                                        n_jobs = -1, scoring = 'f1_macro'))

# Creating a study and performing hyperparameter tuning for 10 trials 
knn_study = optuna.create_study(direction = 'maximize')
knn_study.optimize(objective, n_trials = 10)

# Fitting the best hyperparameters to the model
pipe.set_params(**knn_study.best_params)
pipe.fit(train_x2, train_y)


pickle.dump(pipe, open('model.pkl', 'wb'))
