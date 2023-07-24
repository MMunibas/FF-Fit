import numpy as np
import pandas as pd

from ff_energy.uncertainty.bootstrap import calculate_bootstrap_uncertainty
from ff_energy.uncertainty.cross_val import calculate_cross_val_uncertainty, \
    calculate_std_uncertainty
from ff_energy.uncertainty.mapie import calculate_mapie_uncertainty
from ff_energy.uncertainty.pipe import standardize
from ff_energy.uncertainty.bayes import calculate_bayesian_uncertainty
from ff_energy.uncertainty.conformal import calculate_conformal_uncertainty


class UncertaintyQuantifier:
    def __init__(self, data: pd.DataFrame, ref_key=None, key=None):
        self.cross_val_uncertainty = None
        self.std_uncertainty = None
        self.mapie_uncertainty = None
        self.bootstrap_uncertainty = None
        self.bayesian_uncertainty = None
        self.conformal_uncertainty = None

        self.data = data
        if key is None:
            self.key = "Ens"
        else:
            self.key = key
        if ref_key is None:
            self.ref_key = "Eref"
        else:
            self.ref_key = ref_key

        self.output_dict = self.calculate_uncertainty()

    def __repr__(self):
        return f"UncertaintyQuantifier(data={self.data})"

    def __str__(self):
        return f"UncertaintyQuantifier(data={self.data})"

    def calculate_uncertainty(self, split=0.8):
        self.data["TARGET"] = self.data[self.ref_key]
        self.data["FIT"] = self.data[self.key]
        self.data["SE"] = self.data["FIT"].std() / np.sqrt(self.data["FIT"].shape[0])
        # standardize the data
        self.data["FIT_scaled"] = self.data["FIT"].pipe(standardize)
        self.data["TARGET_scaled"] = self.data["TARGET"].pipe(standardize)
        self.data["SE_scaled"] = self.data["SE"].pipe(standardize)
        # Calculate the residuals
        residuals = self.data[self.ref_key] - self.data[self.key]
        #  create a test-train split
        train_idx = np.random.choice(
            self.data.index, size=int(len(self.data) * split),
            replace=False
        )
        test_idx = self.data.index[~self.data.index.isin(train_idx)]

        data_dict = {
            'X': self.data.drop(columns=[self.ref_key]),
            'y': self.data[self.key],
            'residuals': residuals,
            "std": np.std(residuals),
            "test_std": np.std(residuals[test_idx]) * np.ones(len(test_idx)),
            "train_std": np.std(residuals[train_idx]) * np.ones(len(train_idx)),
            "y_train": self.data.loc[train_idx, self.key],
            "y_test": self.data.loc[test_idx, self.key],
            "y_pred": self.data.loc[train_idx, self.key],
            "y_test_pred": self.data.loc[test_idx, self.key],
            "X_train": self.data.loc[train_idx, self.key],
            "X_test": self.data.loc[test_idx, self.key],
        }

        # Calculate the uncertainty using conformal predictions
        conformal_uncertainty = calculate_conformal_uncertainty(data_dict)
        self.conformal_uncertainty = conformal_uncertainty

        # Calculate the uncertainty using Bayesian statistics
        bayesian_uncertainty = calculate_bayesian_uncertainty(self.data)
        self.bayesian_uncertainty = bayesian_uncertainty

        # Calculate the uncertainty using bootstrap resampling
        bootstrap_uncertainty = calculate_bootstrap_uncertainty(self.data)
        self.bootstrap_uncertainty = bootstrap_uncertainty

        # Calculate the uncertainty using cross-validation
        cross_val_uncertainty = calculate_cross_val_uncertainty(data_dict)
        self.cross_val_uncertainty = cross_val_uncertainty

        # Calculate the uncertainty using MAPPIE
        mapie_uncertainty = calculate_mapie_uncertainty(data_dict)
        self.mapie_uncertainty = mapie_uncertainty

        # standard dev. uncertainty
        std_uncertainty = calculate_std_uncertainty(data_dict)
        self.std_uncertainty = std_uncertainty

        out_dict = {
            'conformal_uncertainty': conformal_uncertainty,
            'bayesian_uncertainty': bayesian_uncertainty,
            'bootstrap_uncertainty': bootstrap_uncertainty,
            'cross_val_uncertainty': cross_val_uncertainty,
            'mapie_uncertainty': mapie_uncertainty,
            'std_uncertainty': std_uncertainty,
        }

        return out_dict
