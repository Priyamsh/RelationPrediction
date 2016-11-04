import numpy as np
import tensorflow as tf
from scipy.sparse import csr_matrix, coo_matrix
import scipy.sparse as sps
import scipy

class Encoder():

    settings = None
    
    def __init__(self, encoder_settings):
        self.settings = encoder_settings

        self.entity_count = int(self.settings['EntityCount'])
        self.relation_count = int(self.settings['RelationCount'])
        self.embedding_width = int(self.settings['EmbeddingWidth'])
        self.regularization_parameter = float(self.settings['RegularizationParameter'])
        self.message_dropout_probability = float(self.settings['MessageDropoutProbability'])
        self.n_convolutions = int(self.settings['NumberOfConvolutions'])
        
    def preprocess(self, triplets):
        triplets = np.array(triplets).transpose()
        
        relations = triplets[1]

        sender_indices = np.hstack((triplets[0], triplets[2])).astype(np.int32)
        receiver_indices = np.hstack((triplets[2], triplets[0])).astype(np.int32)
        message_types = np.hstack((triplets[1], triplets[1]+self.relation_count)).astype(np.int32)

        message_indices = np.arange(receiver_indices.shape[0], dtype=np.int32)
        values = np.ones_like(receiver_indices, dtype=np.int32)

        message_to_receiver_matrix = coo_matrix((values, (receiver_indices, message_indices)), shape=(self.entity_count, receiver_indices.shape[0]), dtype=np.float32).tocsr()

        degrees = (1 / message_to_receiver_matrix.sum(axis=1)).tolist()
        degree_matrix = sps.lil_matrix((self.entity_count, self.entity_count))
        degree_matrix.setdiag(degrees)

        scaled_message_to_receiver_matrix = degree_matrix * message_to_receiver_matrix
        rows, cols, vals = sps.find(scaled_message_to_receiver_matrix)

        #Create TF message-to-receiver matrix:
        self.MTR = tf.SparseTensor(np.array([rows,cols]).transpose(), vals.astype(np.float32), [self.entity_count, receiver_indices.shape[0]])

        #Create TF sender-to-message matrix:
        self.STM = tf.constant(sender_indices, dtype=np.int32)

        #Create TF message type list:
        self.R = tf.constant(message_types, dtype=np.int32)
        
    def initialize_test(self):
        self.X = tf.placeholder(tf.int32, shape=[None,3])

    def initialize_train(self):
        embedding_initial = np.random.randn(self.entity_count, self.embedding_width).astype(np.float32)
        type_initial = np.random.randn(self.relation_count*2+1, self.embedding_width).astype(np.float32)

        convolution_initials_p = [np.random.randn(self.embedding_width, self.embedding_width).astype(np.float32)
                                for _ in range(self.n_convolutions)]
        
        relation_initial = np.random.randn(self.relation_count, self.embedding_width).astype(np.float32)

        self.X = tf.placeholder(tf.int32, shape=[None,3])

        self.W_embedding = tf.Variable(embedding_initial)
        self.W_type = tf.Variable(type_initial)
        self.W_convolutions_p = [tf.Variable(init) for init in convolution_initials_p]
        
        self.W_relation = tf.Variable(relation_initial)
        
    def get_vertex_embedding(self, training=False):
        vertex_embedding = self.W_embedding
        type_embedding = self.W_type

        #No activation for first layer. Maybe subject to change.
        activated_embedding = vertex_embedding

        T = tf.nn.embedding_lookup(type_embedding, self.R)
        for W_layer_p in self.W_convolutions_p:

            #Gather values from vertices in message matrix:
            M = tf.nn.embedding_lookup(activated_embedding, self.STM)

            #Transform messages according to types:
            M_prime = tf.squeeze(tf.mul(M, T))
                
            if training:
                M_prime = tf.nn.dropout(M_prime, self.message_dropout_probability)

            #Construct new vertex embeddings:
            mean_message = tf.sparse_tensor_dense_matmul(self.MTR, M_prime)

            vertex_embedding = mean_message

            if training:
                activated_embedding = tf.nn.dropout(activated_embedding, self.message_dropout_probability)
                
            vertex_embedding += tf.matmul(activated_embedding, W_layer_p)
            
            activated_embedding = tf.nn.relu(vertex_embedding)

        #No activation for final layer:
        return vertex_embedding
        
    def get_all_subject_codes(self):
        return self.get_vertex_embedding()
    
    def get_all_object_codes(self):
        return self.get_vertex_embedding()
    
    def get_weights(self):
        return [self.W_embedding, self.W_relation, self.W_type] + self.W_convolutions_p

    def get_input_variables(self):
        return [self.X]

    def encode(self, training=True):
        self.e1s = tf.nn.embedding_lookup(self.get_vertex_embedding(), self.X[:,0])
        self.rs = tf.nn.embedding_lookup(self.W_relation, self.X[:,1])
        self.e2s = tf.nn.embedding_lookup(self.get_vertex_embedding(), self.X[:,2])

        return self.e1s, self.rs, self.e2s

    def get_regularization(self):
        regularization = tf.reduce_mean(tf.square(self.e1s))
        regularization += tf.reduce_mean(tf.square(self.rs))
        regularization += tf.reduce_mean(tf.square(self.e2s))

        return self.regularization_parameter * regularization

    #Hack
    def parameter_count(self):
        return 4

    def assign_weights(self, weights):
        self.W_embedding = tf.Variable(weights[0])
        self.W_relation = tf.Variable(weights[1])
        self.W_type = tf.Variable(weights[2])
        self.W_convolutions_p = [tf.Variable(weights[3])]
