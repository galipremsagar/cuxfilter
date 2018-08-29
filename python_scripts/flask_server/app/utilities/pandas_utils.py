from pyarrow import RecordBatchStreamReader
import pandas as pd
import json
import os
import numpy as np
import time
import sys


class pandas_utils:
    pandas_df = None
    back_up_dimension_pandas = None
    dimensions_filters = {}
    group_by_backups = {}

    def __init__(self):
        self.pandas_df = None
        self.back_up_dimension_pandas = None
        self.dimensions_filters = {}
        self.group_by_backups = {}


    def hist_numpy(self,data,bins):
        '''
            description:
                Calculate histogram leveraging gpu via pycuda(using numba jit)
            input:
                data: np array, bins: number of bins in the histogram
            Output:
                json -> {X:[__values_of_colName_with_max_64_bins__], Y:[__frequencies_per_bin__]}
        '''
        print("calculating histogram pandas/np version")
        df1 = np.histogram(np.array(data),bins=bins)
        dict_temp ={}

        dict_temp['X'] = list(df1[1].astype(float))[1:]
        dict_temp['Y'] = list(df1[0].astype(float))

        return json.dumps(dict_temp)


    def get_columns(self):
        '''
            description:
            Column names in a data frame
            input:
                data: pandas df
            Output:
                list of column names
        '''
        return str(list(self.pandas_df.columns))

    def read_arrow_to_DF(self,source):
        '''
            description:
                Read arrow file from disk using apache pyarrow
            input:
                source: file path
            return:
                pandas dataframe
        '''
        source = source+".arrow"
        self.pandas_df = RecordBatchStreamReader(source).read_all().to_pandas()
        self.back_up_dimension_pandas = self.pandas_df
        return "data read successfully"


    def read_data(self,load_type,file):
        '''
            description:
                Read file as per the load type
            input:
                load_type: csv or arrow
                file: file path
            return:
                pandas dataframe
        '''
        #file is in the uploads/ folder, so append that to the path
        file = str("/usr/src/app/node_server/uploads/"+file)
        status = self.read_arrow_to_DF(file)
        return status

    def default(self,o):
        if isinstance(o, np.int32): return int(o)
        if isinstance(o, np.int64): return int(o)
        if isinstance(o, np.float32): return float(o)
        if isinstance(o, np.float64): return float(o)
        raise TypeError

    def parse_dict(self,data):
        '''
            description:
                get parsed string format of the dictionary, that can be sent to the socket-client
            input:
                data: dataframe
            return:
                shape string
        '''
        try:
            temp_dict = {}
            for i in data:
                temp_dict[i] = list(data[i].values())
            return json.dumps(temp_dict,default=self.default)
        except Exception as e:
            return str(e)

    def get_size(self):
        '''
            description:
                get shape of the dataframe
            input:
                data: dataframe
            return:
                shape tuple
        '''
        try:
            return str((len(self.pandas_df),len(self.pandas_df.columns)))
        except Exception as e:
            return str(e)

    def reset_filters(self, data, omit=None, include_dim=['all']):
        '''
            description:
                reset filters on the data_gpu dataframe by executing all filters in the dimensions_filters dictionary
            input:
                data: dataset
                omit: column name, the filters associated to which, are to be omitted
                include_dim: list of column_names, which are to be included along with dimensions_filters.keys(); ['all'] to include all columns

            Output:
                result dataframe after executing the filters using the dataframe.query() command
        '''
        # global dimensions_filters
        # print("inside reset filters")
        try:
            temp_list = []
            for key in self.dimensions_filters.keys():
                if omit is not None and omit == key:
                    continue
                if len(self.dimensions_filters[key])>0:
                    temp_list.append(self.dimensions_filters[key])
            query = ' and '.join(temp_list)
            if(len(query) >0):
                # return data.query(query)
                if include_dim[0] == 'all':
                    return data.query(query)
                else:
                    column_list = list(set(list(self.dimensions_filters.keys())+include_dim))
                    return data.loc[:,column_list].query(query)
            else:
                return data

        except Exception as e:
            return str(e)


    def reset_all_filters(self):
        '''
            description:
                reset all filters on all dimensions for the dataset
            input:
                None
            Output:
                number_of_rows_left
        '''
        try:
            self.pandas_df = self.back_up_dimension_pandas
            self.dimensions_filters.clear()
            return str(len(self.pandas_df))

        except Exception as e:
            return str(e)

    def dimension_load(self, dimension_name):
        '''
            description:
                load a dimension
            Get parameters:
                dimension_name (string)
            Response:
                status -> success: dimension loaded successfully/dimension already exists   // error: "groupby not initialized"
        '''
        try:
            if dimension_name not in self.dimensions_filters:
                self.dimensions_filters[dimension_name] = ''
                res = 'dimension loaded successfully'
            else:
                res = 'dimension already exists'
            return res

        except Exception as e:
            return str(e)


    def dimension_reset(self, dimension_name):
        '''
            description:
                reset all filters on a dimension for pandas df
            Get parameters:
                dimension_name (string)
            Response:
                number_of_rows
        '''
        try:
            self.pandas_df = self.back_up_dimension_pandas
            self.dimensions_filters[dimension_name] = ''
            self.pandas_df = self.reset_filters(self.pandas_df)
            return str(len(self.pandas_df))

        except Exception as e:
            return str(e)

    def dimension_get_max_min(self, dimension_name):
        '''
            description:
                get_max_min for a dimension for pandas
            Get parameters:
                dimension_name (string)
            Response:
                max_min_tuple
        '''
        try:
            max_min_tuple = (float(self.pandas_df[dimension_name].max()), float(self.pandas_df[dimension_name].min()))
            return str(max_min_tuple)

        except Exception as e:
            return str(e)

    def dimension_hist(self, dimension_name, num_of_bins):
        '''
            description:
                get histogram for a dimension for pandas
            Get parameters:
                dimension_name (string)
                num_of_bins (integer)
            Response:
                string(json) -> "{X:[__values_of_colName_with_max_64_bins__], Y:[__frequencies_per_bin__]}"
        '''
        try:
            num_of_bins = int(num_of_bins)
            # start = time.time()
            if len(self.dimensions_filters.keys()) == 0 or (dimension_name not in self.dimensions_filters) or (dimension_name in self.dimensions_filters and self.dimensions_filters[dimension_name] == ''):
                return str(self.hist_numpy(self.pandas_df[str(dimension_name)].values,num_of_bins))
            else:
                temp_df = self.reset_filters(self.back_up_dimension_pandas, omit=dimension_name, include_dim = [dimension_name])
                # reset_filters_time = time.time() - start
                return str(self.hist_numpy(temp_df[str(dimension_name)].values,num_of_bins))#+":::"+str(reset_filters_time)

        except Exception as e:
            return str(e)



    def dimension_filterOrder(self, dimension_name, sort_order, num_rows, columns):
        '''
            description:
                get columns values by a filterOrder(all, top(n), bottom(n)) sorted by dimension_name
            Get parameters:
                dimension_name (string)
                sort_order (string): top/bottom/all
                num_rows (integer): OPTIONAL -> if sort_order= top/bottom
                columns (string): comma separated column names
            Response:
                string(json) -> "{col_1:[__row_values__], col_2:[__row_values__],...}"
        '''
        # print(args)
        # print(columns)
        try:
            columns = columns.split(',')
            if(len(columns) == 0 or columns[0]==''):
                columns = list(self.pandas_df.columns)
            elif dimension_name not in columns:
                columns.append(dimension_name)
            print("requested columns",columns)
            print("available columns",self.pandas_df.columns)

            if 'all' == sort_order:
                temp_df = self.pandas_df.loc[:,columns].to_dict()
            else:
                num_rows = int(num_rows)
                max_rows = max(len(self.pandas_df)-1,0)
                n_rows = min(num_rows, max_rows)
                if 'top' == sort_order:
                    temp_df = self.pandas_df.loc[:,columns].nlargest(n_rows,[dimension_name]).to_dict()
                elif 'bottom' == sort_order:
                    temp_df = self.pandas_df.loc[:,columns].nsmallest(n_rows,[dimension_name]).to_dict()

            return str(self.parse_dict(temp_df))

        except Exception as e:
            print(e)
            return str(e)

    def dimension_filter(self, dimension_name, comparison_operation, value):
        '''
            description:
                cumulative filter dimension_name by comparison_operation and value
            Get parameters:
                dimension_name (string)
                comparison_operation (string)
                value (float/int)
            Response:
                number_of_rows_left
        '''
        try:
            query = dimension_name+comparison_operation+value
            if dimension_name in self.dimensions_filters:
                if len(self.dimensions_filters[dimension_name])>0:
                    self.dimensions_filters[dimension_name] += ' and '+ query
                else:
                    self.dimensions_filters[dimension_name] = query
            self.pandas_df = self.pandas_df.query(query)
            return str(len(self.pandas_df))

        except Exception as e:
            return str(e)

    def dimension_filter_range(self, dimension_name, min_value, max_value):
        '''
            description:
                cumulative filter_range dimension_name between range [min_value,max_value]
            Get parameters:
                dimension_name (string)
                min_value (integer)
                max_value (integer)
            Response:
                number_of_rows_left
        '''
        try:
            query = dimension_name+">="+min_value+" and "+dimension_name+"<="+max_value
            # print(str(query))
            if dimension_name in self.dimensions_filters:
                if len(self.dimensions_filters[dimension_name])>0:
                    self.dimensions_filters[dimension_name] += ' and '+ query
                else:
                    self.dimensions_filters[dimension_name] = query
            self.pandas_df = self.pandas_df.query(query)
            return str(len(self.pandas_df))

        except Exception as e:
            return str(e)
