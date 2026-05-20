import faiss
import numpy as np


class ANNEngine:
    def __init__(self):
        self.index = None
        self.vectors = None
        self.index_type = None

    def build_index(self, vectors, index_type='hnsw'):
        self.vectors = vectors
        d = vectors.shape[1]

        if index_type == 'flat':
            self.index = faiss.IndexFlatIP(d)

        elif index_type == 'ivf':
            nlist = int(np.sqrt(vectors.shape[0]))
            quantizer = faiss.IndexFlatIP(d)
            self.index = faiss.IndexIVFFlat(quantizer, d, nlist)
            self.index.train(vectors)
            self.index.nprobe = 10

        elif index_type == 'hnsw':
            self.index = faiss.IndexHNSWFlat(d, 32)

        self.index.add(vectors)
        self.index_type = index_type

    def search(self, query_vector, k=10):
        query = np.array(query_vector, dtype=np.float32).reshape(1, -1)
        distances, indices = self.index.search(query, k)
        return distances[0], indices[0]

    def save_index(self, path):
        faiss.write_index(self.index, path)

    def load_index(self, vectors, path):
        self.vectors = vectors
        self.index = faiss.read_index(path)
