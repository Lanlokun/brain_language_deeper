import os
import argparse
import pickle
import numpy as np
import pandas as pd
from scipy.stats import ttest_rel
import fickling

# === Identify brain voxels where booksum versus base is statistically significant ===
# Do this for Characters & Full discourse features


np.random.seed(42)  # Set random seed

from scipy.stats import zscore
def pearson_corr(X,Y):
    return np.mean(zscore(X)*zscore(Y),0)

def extract_all_voxels_pearson(pred_path, discourse_feature):
    loaded = np.load(pred_path, allow_pickle=True)
    preds_t_per_feat = loaded.item()['preds_t']                             # (1191, ~27905)
    test_t_per_feat = loaded.item()['test_t']
    
    TR_one_hot_pkl_path = f'./data/TR_one_hot_for_features/{discourse_feature}.pkl'
    TR_one_hot = fickling.load(open(TR_one_hot_pkl_path, 'rb'))
    TR_indices = np.where(TR_one_hot==1)[0]                                 # List of TR indices: [10, 13,...]
    TR_indices = np.random.choice(TR_indices, size=162, replace=False)      # Randomly select 162 TR indices, with set seed
    TR_indices = np.sort(TR_indices)
    
    preds_t_per_feat = preds_t_per_feat[TR_indices, :]                      # Extract from only the desired TRs
    test_t_per_feat =  test_t_per_feat[TR_indices, :]

    return pearson_corr(preds_t_per_feat, test_t_per_feat)                  # (~27905,)

# === Change these variables ===
out_sig_voxel_dir = '9-pearson-voxels-for-brain-plot/significant_voxel_indicator/all_models'
nlp_model_list = []
nlp_model_list += ['bart-base', 'bart-booksum']
nlp_model_list += ['led-base', 'led-booksum']
nlp_model_list += ['bigbird-base', 'bigbird-booksum']
nlp_model_list += ['long-t5-base', 'long-t5-booksum']
nlp_model_list = list( set(nlp_model_list) )
nlp_model_list.sort()

# seq_len_list = [20]
# layer_list = [6]
seq_len_list = [20, 100, 200, 500]
seq_len_list += [700, 1000]
layer_list = [6, 7, 8, 9, 10, 11, 12]

parser = argparse.ArgumentParser()
parser.add_argument("--discourse_feature", required=True)
parser.add_argument("--subject", required=True)
parser.add_argument("--ttest_alternative", required=True)

args = parser.parse_args()
print(args)

discourse_feature = args.discourse_feature
subject = args.subject
ttest_alternative = args.ttest_alternative

print(f'--- Entered: {discourse_feature}, {subject}, models: {nlp_model_list} ---')
print(f'--- Output: {out_sig_voxel_dir} ---')
base_models_pearson_voxels_list = []
booksum_models_pearson_voxels_list = []

for nlp_model in nlp_model_list:
    if nlp_model.endswith('-booksum'):
        base_or_booksum_voxels_list_to_append = booksum_models_pearson_voxels_list
    else:
        base_or_booksum_voxels_list_to_append = base_models_pearson_voxels_list

    for layer in layer_list:
        for seq_len in seq_len_list:
            pred_path = f'2-encoding_predictions/{nlp_model}/predict_{subject}_with_{nlp_model}_layer_{layer}_len_{seq_len}.npy'
            if not os.path.isfile(pred_path):
                print(f'@@@ Prediction file not found: subject_{subject}_{nlp_model}_layer_{layer}_len_{seq_len}')
                continue
            
            all_voxels_pearson = extract_all_voxels_pearson(pred_path, discourse_feature)
            base_or_booksum_voxels_list_to_append.append(all_voxels_pearson)

base_pearson_voxels_stacked = np.vstack(base_models_pearson_voxels_list)        # (xx, ~27905), xx is # of models*layers*...
booksum_pearson_voxels_stacked = np.vstack(booksum_models_pearson_voxels_list)

n_voxels = base_pearson_voxels_stacked.shape[1]
voxels_significant_indicator_list = []
for voxel_num in range(n_voxels):
    base_pearson_voxels = list( base_pearson_voxels_stacked[:, voxel_num] )
    booksum_pearson_voxels = list( booksum_pearson_voxels_stacked[:, voxel_num] )
    
    statistic, pvalue = ttest_rel(base_pearson_voxels, booksum_pearson_voxels, alternative=ttest_alternative)
    voxels_significant_indicator_list.append( pvalue )

# Save the results for significant voxels
print(f'# voxels <0.05 for {discourse_feature}_{subject}: {len( [x for x in voxels_significant_indicator_list if (x < 0.05)] )}')
sig_voxel_path = os.path.join(out_sig_voxel_dir, 'booksum_minus_base', ttest_alternative, f'{discourse_feature}_{subject}.pkl')
os.makedirs( os.path.dirname(sig_voxel_path), exist_ok=True )
with open(sig_voxel_path, 'wb') as handle:
    pickle.dump(voxels_significant_indicator_list, handle, protocol=pickle.HIGHEST_PROTOCOL)
