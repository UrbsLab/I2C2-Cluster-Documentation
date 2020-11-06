import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import scipy.stats as scs
import random
from sklearn.preprocessing import StandardScaler
from sklearn.experimental import enable_iterative_imputer
from sklearn.impute import IterativeImputer
import csv
import time

'''Phase 1 of Machine Learning Analysis Pipeline:'''

def job(dataset_path,experiment_path,cv_partitions,partition_method,categorical_cutoff,export_exploratory_analysis,export_feature_correlations,export_univariate_plots,class_label,instance_label,match_label,random_state):

    ##EDITABLE CODE#####################################################################################################
    attribute_headers_to_ignore = []
    categorical_attribute_headers = []
    ####################################################################################################################

    job_start_time = time.time()
    random.seed(random_state)
    np.random.seed(random_state)

    dataset_name = dataset_path.split('/')[-1].split('.')[0]
    dataset_ext = dataset_path.split('/')[-1].split('.')[-1]
    if not os.path.exists(experiment_path + '/' + dataset_name):
        os.mkdir(experiment_path + '/' + dataset_name)
    if not os.path.exists(experiment_path + '/' + dataset_name + '/exploratory'):
        os.mkdir(experiment_path + '/' + dataset_name + '/exploratory')

    if dataset_ext == 'csv':
        data = pd.read_csv(dataset_path,na_values='NA',sep=',')
    else: # txt file
        data = pd.read_csv(dataset_path,na_values='NA',sep='\t')

    if export_exploratory_analysis == "True":
        #data.describe().to_csv(experiment_path + '/' + dataset_name + '/exploratory/'+'DescribeDataset.csv')
        #data.dtypes.to_csv(experiment_path + '/' + dataset_name + '/exploratory/'+'DtypesDataset.csv')
        data.nunique().to_csv(experiment_path + '/' + dataset_name + '/exploratory/'+'NumUniqueDataset.csv')

        #Assess Missingness in Attributes
        missing_count = data.isnull().sum()
        missing_count.to_csv(experiment_path + '/' + dataset_name + '/exploratory/'+'FeatureMissingness.csv')

    #Remove instances with missing outcome values
    data = data.dropna(axis=0,how='any',subset=[class_label])
    data = data.reset_index(drop=True)
    data[class_label] = data[class_label].astype(dtype='int64')

    #Remove columns to be ignored in analysis
    data = data.drop(attribute_headers_to_ignore,axis=1)

    #Check class counts and automatically flip class encoding if there are more cases (i.e. 1) than controls (i.e. 0). This pipeline assumes that 0 encodes the majority class.
    class_counts = data[class_label].value_counts()
    class_counts.to_csv(experiment_path + '/' + dataset_name + '/exploratory/'+'ClassCounts.csv')

    #if class_counts.index[0] == 1:
    #    #Swap class labels (so 0 is majority class)(0's to 1's and 1's to 0's)
    #    data[class_label]=data[class_label].replace(to_replace=0, value=2)
    #    data[class_label]=data[class_label].replace(to_replace=1, value=0)
    #    data[class_label]=data[class_label].replace(to_replace=2, value=1)

    if export_exploratory_analysis == "True":
        #Export Class Count Bar Graph
        class_counts.plot(kind='bar')
        plt.ylabel('Count')
        plt.title('Class Counts')
        plt.savefig(experiment_path + '/' + dataset_name + '/exploratory/'+'ClassCounts.png')
        plt.close('all')

    #Identify categorical variables in dataset
    if len(categorical_attribute_headers) == 0:
        if instance_label == "None":
            x_data = data.drop([class_label],axis=1)
        else:
            x_data = data.drop([class_label,instance_label], axis=1)
        categorical_variables = identifyCategoricalFeatures(x_data,categorical_cutoff)
    else:
        categorical_variables = categorical_attribute_headers

    #Feature Correlations
    if export_feature_correlations:
        data_cor = data.drop([class_label],axis=1)
        corrmat = data_cor.corr(method='pearson')
        f,ax=plt.subplots(figsize=(40,20))
        sns.heatmap(corrmat,vmax=1,square=True)
        plt.savefig(experiment_path + '/' + dataset_name + '/exploratory/'+'FeatureCorrelations.png')
        plt.close('all')

    #Univariate Analysis
    if not os.path.exists(experiment_path + '/' + dataset_name + '/exploratory/univariate'):
        os.mkdir(experiment_path + '/' + dataset_name + '/exploratory/univariate')
    p_value_dict = {}
    for column in data:
        if column != class_label and column != instance_label:
            p_value_dict[column] = test_selector(column,class_label,data,categorical_variables)

    #Save p-values to file
    pval_df = pd.DataFrame.from_dict(p_value_dict, orient='index')
    pval_df.to_csv(experiment_path + '/' + dataset_name + '/exploratory/univariate/Significance.csv',index=True)

    if export_univariate_plots:
        sorted_p_list = sorted(p_value_dict.items(),key = lambda item:item[1])
        sig_cutoff = 0.05
        for i in sorted_p_list:
            for j in data:
                if j == i[0] and i[1] <= sig_cutoff: #ONLY EXPORTS SIGNIFICANT FEATURES
                    graph_selector(j,class_label,data,categorical_variables,experiment_path,dataset_name)

    #Get and Export Original Headers
    headers = data.columns.values.tolist()
    headers.remove(class_label)
    if instance_label != "None":
        headers.remove(instance_label)
    if partition_method == 'M':
        headers.remove(match_label)

    with open(experiment_path + '/' + dataset_name + '/exploratory/OriginalHeaders.csv',mode='w') as file:
        writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(headers)
    file.close()

    #Cross Validation
    train_dfs,test_dfs = cv_partitioner(data,cv_partitions,partition_method,class_label,True,match_label,random_state)

    #Save CV'd data as .csv files
    if not os.path.exists(experiment_path + '/' + dataset_name + '/CVDatasets'):
        os.mkdir(experiment_path + '/' + dataset_name + '/CVDatasets')
    counter = 0
    for each in train_dfs:
        a = each.values
        with open(experiment_path + '/' + dataset_name + '/CVDatasets/'+dataset_name+'_CV_' + str(counter) +"_Train.csv", mode="w") as file:
            writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(each.columns.values.tolist())
            for row in a:
                writer.writerow(row)
        counter += 1

    counter = 0
    for each in test_dfs:
        a = each.values
        with open(experiment_path + '/' + dataset_name + '/CVDatasets/'+dataset_name+'_CV_' + str(counter) +"_Test.csv", mode="w") as file:
            writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(each.columns.values.tolist())
            for row in a:
                writer.writerow(row)
        file.close()
        counter += 1

    #Save Runtime
    if not os.path.exists(experiment_path + '/' + dataset_name + '/runtime'):
        os.mkdir(experiment_path + '/' + dataset_name + '/runtime')
    runtime_file = open(experiment_path + '/' + dataset_name + '/runtime/runtime_exploratory.txt','w')
    runtime_file.write(str(time.time()-job_start_time))
    runtime_file.close()

    #Print completion
    print(dataset_name+" phase 1 complete")
    job_file = open(experiment_path + '/jobsCompleted/job_exploratory_'+dataset_name+'.txt', 'w')
    job_file.write('complete')
    job_file.close()

########Univariate##############
def test_selector(featureName, outcomeLabel, td, categorical_variables):
    p_val = 0
    # Feature and Outcome are discrete/categorical/binary
    if featureName in categorical_variables:
        # Calculate Contingency Table - Counts
        table = pd.crosstab(td[featureName], td[outcomeLabel])

        # Univariate association test (Chi Square Test of Independence - Non-parametric)
        c, p, dof, expected = scs.chi2_contingency(table)
        p_val = p

    # Feature is continuous and Outcome is discrete/categorical/binary
    else:
        # Univariate association test (Mann-Whitney Test - Non-parametric)
        c, p = scs.mannwhitneyu(x=td[featureName].loc[td[outcomeLabel] == 0], y=td[featureName].loc[td[outcomeLabel] == 1])
        p_val = p

    return p_val

def graph_selector(featureName, outcomeLabel, td, categorical_variables,experiment_path,dataset_name):
    # Feature and Outcome are discrete/categorical/binary
    if featureName in categorical_variables:
        # Generate contingency table count bar plot. ------------------------------------------------------------------------
        # Calculate Contingency Table - Counts
        table = pd.crosstab(td[featureName], td[outcomeLabel])
        geom_bar_data = pd.DataFrame(table)
        mygraph = geom_bar_data.plot(kind='bar')
        plt.ylabel('Count')
        new_feature_name = featureName.replace(" ","")       # Deal with the dataset specific characters causing problems in this dataset.
        new_feature_name = new_feature_name.replace("*","")  # Deal with the dataset specific characters causing problems in this dataset.
        new_feature_name = new_feature_name.replace("/","")  # Deal with the dataset specific characters causing problems in this dataset.
        plt.savefig(experiment_path + '/' + dataset_name + '/exploratory/univariate/'+'Barplot_'+str(new_feature_name)+".png",bbox_inches="tight", format='png')
        plt.close('all')
    # Feature is continuous and Outcome is discrete/categorical/binary
    else:
        # Generate boxplot-----------------------------------------------------------------------------------------------------
        mygraph = td.boxplot(column=featureName, by=outcomeLabel)
        plt.ylabel(featureName)
        plt.title('')
        new_feature_name = featureName.replace(" ","")       # Deal with the dataset specific characters causing problems in this dataset.
        new_feature_name = new_feature_name.replace("*","")  # Deal with the dataset specific characters causing problems in this dataset.
        new_feature_name = new_feature_name.replace("/","")  # Deal with the dataset specific characters causing problems in this dataset.
        plt.savefig(experiment_path + '/' + dataset_name + '/exploratory/univariate/'+'Boxplot_'+str(new_feature_name)+".png",bbox_inches="tight", format='png')
        plt.close('all')

###################################
def cv_partitioner(td, cv_partitions, partition_method, outcomeLabel, categoricalOutcome, matchName, randomSeed):
    """ Takes data frame (td), number of cv partitions, partition method
    (R, S, or M), outcome label, Boolean indicated whether outcome is categorical
    and the column name used for matched CV. Returns list of training and testing
    dataframe partitions.
    """
    # Partitioning-----------------------------------------------------------------------------------------
    # Shuffle instances to avoid potential biases
    td = td.sample(frac=1, random_state=randomSeed).reset_index(drop=True)

    # Temporarily convert data frame to list of lists (save header for later)
    header = list(td.columns.values)
    datasetList = list(list(x) for x in zip(*(td[x].values.tolist() for x in td.columns)))

    # Handle Special Variables for Nominal Outcomes
    outcomeIndex = None
    classList = None
    if categoricalOutcome:
        outcomeIndex = td.columns.get_loc(outcomeLabel)
        classList = []
        for each in datasetList:
            if each[outcomeIndex] not in classList:
                classList.append(each[outcomeIndex])

    # Initialize partitions
    partList = []  # Will store partitions
    for x in range(cv_partitions):
        partList.append([])

    # Random Partitioning Method----------------------------
    if partition_method == 'R':
        currPart = 0
        counter = 0
        for row in datasetList:
            partList[currPart].append(row)
            counter += 1
            currPart = counter % cv_partitions

    # Stratified Partitioning Method-----------------------
    elif partition_method == 'S':
        if categoricalOutcome:  # Discrete outcome

            # Create data sublists, each having all rows with the same class
            byClassRows = [[] for i in range(len(classList))]  # create list of empty lists (one for each class)
            for row in datasetList:
                # find index in classList corresponding to the class of the current row.
                cIndex = classList.index(row[outcomeIndex])
                byClassRows[cIndex].append(row)

            for classSet in byClassRows:
                currPart = 0
                counter = 0
                for row in classSet:
                    partList[currPart].append(row)
                    counter += 1
                    currPart = counter % cv_partitions

        else:  # Do stratified partitioning for continuous endpoint data
            raise Exception("Error: Stratified partitioning only designed for discrete endpoints. ")

    elif partition_method == 'M':
        if categoricalOutcome:
            # Get match variable column index
            outcomeIndex = td.columns.get_loc(outcomeLabel)
            matchIndex = td.columns.get_loc(matchName)

            # Create data sublists, each having all rows with the same match identifier
            matchList = []
            for each in datasetList:
                if each[matchIndex] not in matchList:
                    matchList.append(each[matchIndex])

            byMatchRows = [[] for i in range(len(matchList))]  # create list of empty lists (one for each match group)
            for row in datasetList:
                # find index in matchList corresponding to the matchset of the current row.
                mIndex = matchList.index(row[matchIndex])
                row.pop(matchIndex)  # remove match column from partition output
                byMatchRows[mIndex].append(row)

            currPart = 0
            counter = 0
            for matchSet in byMatchRows:  # Go through each unique set of matched instances
                for row in matchSet:  # put all of the instances
                    partList[currPart].append(row)
                # move on to next matchset being placed in the next partition.
                counter += 1
                currPart = counter % cv_partitions

            header.pop(matchIndex)  # remove match column from partition output
        else:
            raise Exception("Error: Matched partitioning only designed for discrete endpoints. ")

    else:
        raise Exception('Error: Requested partition method not found.')

    train_dfs = []
    test_dfs = []
    for part in range(0, cv_partitions):
        testList = partList[part]  # Assign testing set as the current partition

        trainList = []
        tempList = []
        for x in range(0, cv_partitions):
            tempList.append(x)
        tempList.pop(part)

        for v in tempList:  # for each training partition
            trainList.extend(partList[v])

        train_dfs.append(pd.DataFrame(trainList, columns=header))
        test_dfs.append(pd.DataFrame(testList, columns=header))

    return train_dfs, test_dfs

###################################
def identifyCategoricalFeatures(x_data,categorical_cutoff):
    """ Takes a dataframe (of independent variables) with column labels and returns a list of column names identified as
    being categorical based on user defined cutoff. """
    categorical_variables = []
    for each in x_data:
        if x_data[each].nunique() <= categorical_cutoff:
            categorical_variables.append(each)
    return categorical_variables

if __name__ == '__main__':
    job(sys.argv[1],sys.argv[2],int(sys.argv[3]),sys.argv[4],int(sys.argv[5]),sys.argv[6],sys.argv[7],sys.argv[8],sys.argv[9],sys.argv[10],sys.argv[11],int(sys.argv[12]))
