import socket
import select


class CentreRegulation:

    def __init__(self, hote="0.0.0.0", port_tcp=5050,
                 port_udp=5051, base="sae_missions.db"):

        self.hote = hote
        self.port_tcp = port_tcp

        self.serveur = None
        self.clients = []

    def demarrer(self):

        # Création du serveur TCP
        self.serveur = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Adresse et port
        self.serveur.bind((self.hote, self.port_tcp))

        # Attendre les clients
        self.serveur.listen()

        print("Serveur démarré sur le port", self.port_tcp)

    def executer(self):

        self.demarrer()

        while True:

            # Surveiller le serveur et les clients
            sockets = [self.serveur] + self.clients

            prets, _, _ = select.select(sockets, [], [])

            for sock in prets:

                # Nouveau client
                if sock == self.serveur:

                    client, adresse = self.serveur.accept()

                    self.clients.append(client)

                    print("Client connecté :", adresse)

                # Message reçu
                else:

                    message = sock.recv(1024)

                    if message:

                        texte = message.decode()

                        print("Message reçu :", texte)

                        sock.send("Message reçu par le serveur".encode())

                    else:

                        sock.close()

                        self.clients.remove(sock)

                        print("Client déconnecté")

    def arreter(self):

        for client in self.clients:
            client.close()

        if self.serveur:
            self.serveur.close()