import os
import json
# basics
# %matplotlib inline
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import matplotlib
import numpy as np
import random
random.seed(12121)
np.random.seed(12121)

from gym.player.vnfbr import VNFBR


def select_and_rename(df, mapping):
    """
    Helper: Selects columns of df using the keys
    of the mapping dict.
    It renames the columns to the values of the
    mappings dict.
    """
    # select subset of columns
    dff = df[list(mapping.keys())]
    # rename 
    for k, v in mapping.items():
        #print("Renaming: {} -> {}".format(k, v))
        dff.rename(columns={k: v}, inplace=True)
    #print(dff.head())
    return dff

def cleanup(df):
    """
    Cleanup of df data.
    Dataset specific.
    """
    def _replace(df, column, str1, str2):
        if column in df:
            df[column] = df[column].str.replace(str1, str2)
            
    def _to_num(df, column):
        if column in df:
            df[column] = pd.to_numeric(df[column])
        
    _replace(df, "flow_size", "smallFlows.pcap", "small")   
    _replace(df, "flow_size", "bigFlows.pcap", "big")
    #_to_num(df, "flow_size")
    _replace(df, "ruleset", "./start.sh small_ruleset", "small")
    _replace(df, "ruleset", "./start.sh big_ruleset", "big")
    _replace(df, "ruleset", "./start.sh empty", "empty")
    #_to_num(df, "ruleset")
    


map_columns = {
    "input_settings_agent_one_pcap": "flow_size",
    "input_sut_entrypoint": "ruleset",
    "input_sut_resources_cpu_bw": "cpu_bw",
    "monitor_metric_bytes": "suricata_bytes",
    "monitor_metric_packets": "suricata_packets",
    "monitor_metric_dropped": "suricata_dropped",
    "monitor_metric_drops": "suricata_drops",
    "test": "test",
    "trial": "trial",
}


def finish():
    plt.cla()
    plt.clf()
    plt.close()

def save_fig(fig_id, tight_layout=True, fig_extension="png", fig_size=(8, 6), resolution=500):

    root_folder = os.path.normpath(
                os.path.join(
                    os.path.dirname(__file__), "./gfx"))

    path = os.path.join(root_folder, fig_id + "." + fig_extension)
    print("Saving figure", fig_id)
    if tight_layout:
        plt.tight_layout()
    plt.savefig(path, format=fig_extension, figsize=fig_size, dpi=resolution)
    finish()



def analyze_vnfbr():
    filepath = os.path.normpath(
                os.path.join(
                    os.path.dirname(__file__), "vnfbr/vnfbr-003"))

    vnfbr = VNFBR()
    vnfbr.load(filepath)

    df = vnfbr.extract()
    print("Total number of reports", len(df))

    # print all the metric names and input params contained in vnfpp reports
    # metrics_names = list(df_raw.columns.values)
    # print(metrics_names)

    return df

df_raw = analyze_vnfbr()
df_raw["vnf"] = "suricata"

# cleanup data sets
dfs_raw = [df_raw]
map_list = [map_columns]
dfs = list()  # clean data frames
for (df, m) in zip(dfs_raw, map_list):
    tmp = select_and_rename(df.copy(), m)
    cleanup(tmp)
    dfs.append(tmp)
    
df = dfs[0]
print(df)

def plots(df):    
    sns.catplot(data=df, x="cpu_bw", y="suricata_packets", hue="ruleset", col="flow_size", kind="bar")
    save_fig("cat1")
    sns.catplot(data=df, x="cpu_bw", y="suricata_drops", hue="ruleset", col="flow_size", kind="bar")
    save_fig("cat2")
    
# plots(df)