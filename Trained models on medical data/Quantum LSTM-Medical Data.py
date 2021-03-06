from datetime import datetime

#Importer des bibio
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from keras.preprocessing.sequence import TimeseriesGenerator
from keras.models import Sequential
from keras.layers import Dense, LSTM, Dropout, Activation,Bidirectional
from tensorflow.keras.callbacks import EarlyStopping
from tensorflow import keras
import tensorflow as tf
import pennylane as qml
from pennylane.operation import Operation, AnyWires
import time

#******** Étape 1: Collecte des données *********************
url = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_time_series/time_series_covid19_confirmed_global.csv"
df_confirmed = pd.read_csv(url)

country = 'Tunisia';
df_confirmed1 = df_confirmed[df_confirmed["Country/Region"] == country]


##******************* structuring times eries data *************
df_confirmed2 = pd.DataFrame(df_confirmed1[df_confirmed1.columns[4:]].sum(),columns=["confirmed"])
df_confirmed2.index = pd.to_datetime(df_confirmed2.index,format='%m/%d/%y')
df_confirmed2.tail()
df_new = df_confirmed2[["confirmed"]]
print(df_new)

#*************Étape 2: prétraitement des données******************

#daily data and i want to predict 5 days afterwards
#ensemble de validation serait de 5 points de données et le reste serait l'ensemble d'apprentissage.
x = len(df_new)-5
train=df_new.iloc[:x]
test = df_new.iloc[x:]
print(train);

scaler = MinMaxScaler()

#find max value
scaler.fit(train)
scaled_train = scaler.transform(train)#and divide every point by max value
scaled_test = scaler.transform(test)
print(scaled_train[-5:])

#***********Générateur de séries temporelles****************
## how to decide num of inputs

n_input = 5  ## number of steps
n_features = 1 ## number of features you want to predict (for univariate time series n_features=1)
generator = tf.keras.preprocessing.sequence.TimeseriesGenerator(scaled_train,scaled_train,length = n_input,batch_size=1)


len(scaled_train)
len(generator)
x,y = generator[50]
(x.shape,y.shape)
(x,y)
#x → Réseau de neurones
#y - mise à jour des pondérations
print((x,y))
#Quantum Model

n_qubits = 4
dev = qml.device('default.qubit', wires=n_qubits)

@qml.qnode(dev)
def qnode(inputs, weights_0, weight_1):
    qml.RX(inputs[0], wires=0)
    qml.RX(inputs[1], wires=1)
    qml.Rot(*weights_0, wires=0)
    qml.RY(weight_1, wires=1)
    qml.CNOT(wires=[0, 1])
    return qml.expval(qml.PauliZ(0)), qml.expval(qml.PauliZ(1))
weight_shapes = {"weights_0": 3, "weight_1":1}
#************* Construction du modèle LSTM ***************


clayer1 = tf.keras.layers.LSTM(15,activation="relu",input_shape=(n_input,n_features))

calyer3 = tf.keras.layers.Dense(75)
qlayer = qml.qnn.KerasLayer(qnode, weight_shapes, output_dim=2)
clayer6 = tf.keras.layers.Dense(1)
hybrid_model = tf.keras.models.Sequential([clayer1,qlayer,clayer6])
opt = tf.keras.optimizers.SGD(learning_rate=0.5)
dot_img_file = '../Dataset/model_simple_lstm_quantum_medical.png'
tf.keras.utils.plot_model(hybrid_model, to_file=dot_img_file, show_shapes=True)
hybrid_model.compile(opt, loss='mae')

print("*****")
print(hybrid_model.layers)
print("*****")
#***** validation set *******
validation_set = np.append(scaled_train[55],scaled_test)
validation_set= validation_set.reshape(6,1) #A verifier
validation_set

## how to decide num of inputs ,
n_input = 5
n_features = 1
validation_gen = tf.keras.preprocessing.sequence.TimeseriesGenerator(validation_set,validation_set,length=5,batch_size=1)
print("validation_gen")
print(validation_gen)
validation_gen[0][0].shape,validation_gen[0][1].shape
start = time.time()
#Entraîner le modèle
early_stop = EarlyStopping(monitor='val_loss',patience=20,restore_best_weights=True)
hybrid_model.fit(generator,validation_data=validation_gen,epochs=100,callbacks=[early_stop],steps_per_epoch=10)

#100 itération
# « restore_best_weights» qui prend le meilleur poids des itérations
x = hybrid_model.fit(generator,validation_data=validation_gen,epochs=100,callbacks=[early_stop],steps_per_epoch=10)
print(x)
print("The time used to execute this is given below")
end = time.time()
print(end - start)
#****************  Performance du modèle *************

hybrid_model.history.history.keys()
myloss = hybrid_model.history.history["val_loss"]
plt.title("validation loss vs epochs")
plt.plot(range(len(myloss)),myloss)

#prévision
## holding predictions


test_prediction = []

##last n points from training set
first_eval_batch = scaled_train[-n_input:]
current_batch = first_eval_batch.reshape(1,n_input,n_features)

current_batch.shape
print("******")
print(current_batch)
print(current_batch.shape)

## how far in future we can predict
for i in range(len(test)+7):
    current_pred = hybrid_model.predict(current_batch)[0]
    print("current_pred")
    print(current_pred)
    test_prediction.append(current_pred)
    current_batch = np.append(current_batch[:,1:,:], [[current_pred]], axis=1)
print(test_prediction)
print(current_pred)
print("*****")
print(hybrid_model.build(input_shape=(n_input,n_features)))
print(hybrid_model.summary())
print("*****")
### inverse scaled data
#La sortie est une donnée normalisée, nous appliquons donc des transformations inverses aux éléments suivant
true_prediction = scaler.inverse_transform(test_prediction)
true_prediction[:,0]

time_series_array = test.index
for k in range(0,7):
    time_series_array = time_series_array.append(time_series_array[-1:] + pd.DateOffset(1))
time_series_array
df_forecast = pd.DataFrame(columns=["confirmed","confirmed_predicted"],index=time_series_array)


df_forecast.loc[:,"confirmed_predicted"] = true_prediction[:,0]
df_forecast.loc[:,"confirmed"] = test["confirmed"]

print(df_forecast)
df_forecast.plot(title="Tunisia Predictions for next 7 days")
plt.show()

#****MAPE******
MAPE = np.mean(np.abs(np.array(df_forecast["confirmed"][:5]) - np.array(df_forecast["confirmed_predicted"][:5]))/np.array(df_forecast["confirmed"][:5]))
print("MAPE is " + str(MAPE*100) + " %")

#****RMSE******
from math import sqrt
from sklearn.metrics import mean_squared_error
#****RMSE******
RMSE = sqrt(mean_squared_error(np.array(df_forecast["confirmed"][:5]),np.array(df_forecast["confirmed_predicted"][:5])))

print("RMSE is " + str(round(RMSE,3)))
#****stdev******
stdev = np.sqrt(1/(5-2) * RMSE)
print(stdev)
 #****MAE
mae = np.mean(np.abs((df_forecast["confirmed"][:5]) - np.array(df_forecast["confirmed_predicted"][:5])))
print("MAE is " + str(mae) + " %")

# calculate prediction interval
interval = 1.96 * stdev
print("prediction interval is " + str(interval))


df_forecast["confirm_min"] = df_forecast["confirmed_predicted"] - interval
df_forecast["confirm_max"] = df_forecast["confirmed_predicted"] + interval
print(df_forecast)

df_forecast["Model Accuracy"] = round((1-MAPE),2)
print(df_forecast)

fig= plt.figure(figsize=(8,5))
plt.title("{} - Results".format('Tunisia'))
plt.plot(df_forecast.index,df_forecast["confirmed"],label="confirmed")
plt.plot(df_forecast.index,df_forecast["confirmed_predicted"],label="confirmed_predicted")
#ax.fill_between(x, (y-ci), (y+ci), color='b', alpha=.1)
plt.fill_between(df_forecast.index,df_forecast["confirm_min"],df_forecast["confirm_max"],color="indigo",alpha=0.1,label="Confidence Interval")
plt.legend()
plt.show()
