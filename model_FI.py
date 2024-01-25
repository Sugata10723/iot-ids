import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import OneHotEncoder
from sklearn.cluster import MiniBatchKMeans
import xgboost as xgb
import sklearn.preprocessing as preprocessing
import plotter 
import matplotlib.pyplot as plt


#################################################################################   
# パラメータ
# k: クラスタ数
# n_fi: 特徴量選択における重要な特徴量の数
# n_pca: 特徴量選択におけるPCAによる特徴抽出の次元数
# n_estimators: Isolation Forestの決定木の数
# max_samples: Isolation Forestのサンプル数
# contamination: Isolation Forestの外れ値の割合
#################################################################################


class AnomalyDetector_FI:
    def __init__(self, k, n_fi, c_attack, c_normal, categorical_columns=None):
        self.k = k
        self.n_estimators = 50
        self.max_samples = 100
        self.c_attack = c_attack
        self.c_normal = c_normal
        self.n_fi = n_fi
        self.categorical_columns = categorical_columns
        self.ohe = preprocessing.OneHotEncoder(sparse_output=False, categories='auto', handle_unknown='ignore')
        self.mm = preprocessing.MinMaxScaler()
        self.important_features = None
        self.sampled_attack = None
        self.sampled_normal = None
        self.iforest_attack = None
        self.iforest_normal = None
        # プロットのため
        self.attack_data = None
        self.normal_data = None
        self.normal_prd = None
        self.attack_prd = None

    def splitsubsystem(self, X, y):
        attack_indices = np.where(y == 1)[0]
        normal_indices = np.where(y == 0)[0]
        return X[attack_indices], X[normal_indices]

    def feature_selection(self, data, y):
        # 全体に対してFIを用いて特徴量選択
        xgb_model = xgb.XGBClassifier() # 使用するモデルは要検討
        xgb_model.fit(data, y)
        feature_importances = xgb_model.feature_importances_
        important_features = np.argsort(feature_importances)[::-1][:self.n_fi]
        data_fi = data[:, important_features]

        return data_fi, important_features 

    def get_nearest_points(self, data, kmeans):
        distances = kmeans.transform(data[:, :-1])
        nearest_points = []
        for i in range(kmeans.n_clusters):
            cluster_indices = np.where(data[:, -1] == i)[0]
            if len(cluster_indices) > 0:  # k-meansの特性より、空のクラスタが存在する可能性がある
                nearest_index = cluster_indices[np.argmin(distances[cluster_indices, i])]
                nearest_points.append(data[nearest_index])
        nearest_points = np.array(nearest_points)
        nearest_points = nearest_points[:, :-1]  # 'cluster' columnを削除
        return nearest_points

    def make_cluster(self, data):
        if len(data) < self.k: # サンプル数がkより小さい場合はそのまま返す
            return data
        else:
            kmeans = MiniBatchKMeans(n_clusters=self.k, init='k-means++', batch_size=100, tol=0.01, n_init=10) 
            clusters = kmeans.fit_predict(data)
            data = np.column_stack((data, clusters))
            data_sampled = self.get_nearest_points(data, kmeans)
            return data_sampled

    def fit(self, X, y):
        ## Preprocessing X: Pandas DataFrame, y: NumPy Array
        # one-hotエンコード 入力：DataFrame　出力：ndarray
        X_ohe = self.ohe.fit_transform(X[self.categorical_columns])
        X_num = X.drop(columns=self.categorical_columns, inplace=False).values
        # 正規化 入力：ndarray　出力：ndarray
        X_num = self.mm.fit_transform(X_num)
        X_processed = np.concatenate([X_ohe, X_num], axis=1)
        # 特徴量選択 入力：ndarray 出力: ndarray
        X_fi, self.important_features = self.feature_selection(X_processed, y)
        # サブシステムに分割 入力：ndarray　出力：ndarray
        self.attack_data, self.normal_data = self.splitsubsystem(X_fi, y)
        # サンプリング 入力：ndarray　出力：ndarray
        self.sampled_attack = self.make_cluster(self.attack_data)
        self.sampled_normal = self.make_cluster(self.normal_data)
    
        ## training 入力：ndarray
        self.iforest_attack = IsolationForest(n_estimators=self.n_estimators, max_samples=min(self.max_samples, len(self.sampled_attack)), contamination=self.c_attack).fit(self.sampled_attack)
        self.iforest_normal = IsolationForest(n_estimators=self.n_estimators, max_samples=min(self.max_samples, len(self.sampled_normal)), contamination=self.c_normal).fit(self.sampled_normal)

        
    def predict(self, X):
        predictions = []
        total_points = len(X)

        ## preprocessing
        # one-hotエンコード　入力：DataFrame　出力：ndarray
        X_ohe = self.ohe.transform(X[self.categorical_columns])
        X_num = X.drop(columns=self.categorical_columns, inplace=False).values
        # 正規化　入力：ndarray 出力：ndarray
        X_num = self.mm.transform(X_num) # numeicalデータにだけでよい
        # 特徴量選択 入力：ndarray 出力：ndarray    
        X_processed = np.concatenate([X_ohe, X_num], axis=1)
        X_fi = X_processed[:, self.important_features]
    
        ## predict
        attack_prd = self.iforest_attack.predict(X_fi)
        attack_prd = [1 if result == 1 else 0 for result in attack_prd]   
        self.attack_prd = attack_prd
        
        normal_prd = self.iforest_normal.predict(X_fi)
        normal_prd = [1 if result == 1 else 0 for result in normal_prd]
        self.normal_prd = [0 if x == 1 else 1 for x in normal_prd] # normalの判定は逆になる
        
        for i in range(total_points):
            if attack_prd[i] == 0 and normal_prd[i] == 1: # normal
                predictions.append(0)  
            elif attack_prd[i] == 0 and normal_prd[i] == 0: # unknown
                predictions.append(-1)  
            else: # attack
                predictions.append(1)

        return predictions
