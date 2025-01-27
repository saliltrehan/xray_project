import os
import pickle
import sys
import inspect
import pandas as pd
import numpy as np
import inspect
from xray.logger import logging
from xray.exception import CustomException
from xray.entity.config_entity import ModelEvaluationConfig
from xray.entity.artifact_entity import ModelTrainerArtifacts, ModelEvaluationArtifacts, DataTransformationArtifacts
from keras.preprocessing.text import Tokenizer
import tensorflow as tf
from keras.utils import pad_sequences
from xray.ml.model import ModelArchitecture
from xray.constants import *
from xray.configuration.gcloud_syncer import GCloudSync
from sklearn.metrics import confusion_matrix

class ModelEvaluation:
    def __init__(self, 
                 model_evaluation_config: ModelEvaluationConfig, 
                 model_trainer_artifacts: ModelTrainerArtifacts,
                 data_transformation_artifacts: DataTransformationArtifacts):
        
        """
        :param model_evaluation_config: Configuration for model evaluation            
        model = model_architecture.get_model()
        data transformation artifact stage
        :param model_trainer_artifacts: Output reference of model trainer artifact stage
        """

        self.model_evaluation_config = model_evaluation_config
        self.model_trainer_artifacts = model_trainer_artifacts
        self.data_transformation_artifacts = data_transformation_artifacts
        self.gcloud = GCloudSync()


    
    def get_best_model_from_gcloud(self) -> str:
        """
        :return: Fetch best model from gcloud storage and store inside best model directory path
        """
        current_function_name = inspect.stack()[0][3]
        logging.info(f"Entered the {current_function_name} method of {self.__class__.__name__} class")        
        try:
            os.makedirs(self.model_evaluation_config.BEST_MODEL_DIR_PATH, exist_ok=True)

            self.gcloud.sync_folder_from_gcloud(self.model_evaluation_config.BUCKET_NAME,
                                                self.model_evaluation_config.MODEL_NAME,
                                                self.model_evaluation_config.BEST_MODEL_DIR_PATH)

            best_model_path = os.path.join(self.model_evaluation_config.BEST_MODEL_DIR_PATH,
                                           self.model_evaluation_config.MODEL_NAME)
            logging.info(f"Exited the {current_function_name} method of {self.__class__.__name__} class")
            
            return best_model_path
        
        except Exception as e:
            raise CustomException(e, sys) from e 
        

    
    def evaluate(self):
        """

        :param model: Currently trained model or best model from gcloud storage
        :param data_loader: Data loader for validation dataset
        :return: loss
        """
        current_function_name = inspect.stack()[0][3]
        logging.info(f"Entered the {current_function_name} method of {self.__class__.__name__} class")         
        try:
            print(self.model_trainer_artifacts.x_test_path)

            x_test = pd.read_csv(self.model_trainer_artifacts.x_test_path,index_col=0)
            print(x_test)
            y_test = pd.read_csv(self.model_trainer_artifacts.y_test_path,index_col=0)

            with open('tokenizer.pickle', 'rb') as handle:
                tokenizer = pickle.load(handle)

            load_model=tf.keras.models.load_model(self.model_trainer_artifacts.trained_model_path)

            x_test = x_test['tweet'].astype(str)

            x_test = x_test.squeeze()
            y_test = y_test.squeeze()

            test_sequences = tokenizer.texts_to_sequences(x_test)
            test_sequences_matrix = pad_sequences(test_sequences,maxlen=MAX_LEN)
            print(f"----------{test_sequences_matrix}------------------")

            print(f"-----------------{x_test.shape}--------------")
            print(f"-----------------{y_test.shape}--------------")
            accuracy = load_model.evaluate(test_sequences_matrix,y_test)
            logging.info(f"the test accuracy is {accuracy}")

            lstm_prediction = load_model.predict(test_sequences_matrix)
            res = []
            for prediction in lstm_prediction:
                if prediction[0] < 0.5:
                    res.append(0)
                else:
                    res.append(1)
            print(confusion_matrix(y_test,res))
            logging.info(f"the confusion_matrix is {confusion_matrix(y_test,res)} ")
            logging.info(f"Exited the {current_function_name} method of {self.__class__.__name__} class")
            
            return accuracy
        except Exception as e:
            raise CustomException(e, sys) from e
        

    
    def initiate_model_evaluation(self) -> ModelEvaluationArtifacts:
        """
            Method Name :   initiate_model_evaluation
            Description :   This function is used to initiate all steps of the model evaluation

            Output      :   Returns model evaluation artifact
            On Failure  :   Write an exception log and then raise an exception
        """
        current_function_name = inspect.stack()[0][3]
        logging.info(f"Entered the {current_function_name} method of {self.__class__.__name__} class") 
        try:

            logging.info("Loading currently trained model")
            trained_model=tf.keras.models.load_model(self.model_trainer_artifacts.trained_model_path)
            with open('tokenizer.pickle', 'rb') as handle:
                load_tokenizer = pickle.load(handle)

            trained_model_accuracy = self.evaluate()

            logging.info("Fetch best model from gcloud storage")
            best_model_path = self.get_best_model_from_gcloud()

            logging.info("Check is best model present in the gcloud storage or not ?")
            if os.path.isfile(best_model_path) is False:
                is_model_accepted = True
                logging.info("glcoud storage model is false and currently trained model accepted is true")

            else:
                logging.info("Load best model fetched from gcloud storage")
                best_model=tf.keras.models.load_model(best_model_path)
                best_model_accuracy= self.evaluate()

                logging.info("Comparing loss between best_model_loss and trained_model_loss ? ")
                if best_model_accuracy > trained_model_accuracy:
                    is_model_accepted = True
                    logging.info("Trained model not accepted")
                else:
                    is_model_accepted = False
                    logging.info("Trained model accepted")

            model_evaluation_artifacts = ModelEvaluationArtifacts(is_model_accepted=is_model_accepted)
            
            logging.info("Returning the ModelEvaluationArtifacts")
            logging.info(f"Exited the {current_function_name} method of {self.__class__.__name__} class")       
                 
            return model_evaluation_artifacts

        except Exception as e:
            raise CustomException(e, sys) from e