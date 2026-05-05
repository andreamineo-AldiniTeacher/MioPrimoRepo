from flask import Flask, session, request, jsonify
from datetime import timedelta,datetime
import sqlite3

app = Flask(__name__)
app.secret_key = 'chiave segreta'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=25)

def get_db_connection(messaggio):

    conn = sqlite3.connect('biblioteca.db')

    # Abilitiamo i vincoli tra tabelle (Foreign Keys)
    conn.execute("PRAGMA foreign_keys = ON;")

    # Configuriamo l'accesso ai risultati per nome colonna
    conn.row_factory = sqlite3.Row

    return conn

def valida_body_richiesta(data,lista_chiavi):
    if not data:
        return False,'Formato non valido: manca body richiesta'

    if not isinstance(data,dict):
        return False,'Formato non valido: il tipo dato deve essere un dizionario'

    for chiave in lista_chiavi:
        if data.get(chiave)== None:
            return False, f'Formato non valido: manca il campo obbligatorio {chiave}'

    return True,''

@app.route('/api/inserisci_utente',methods=['POST'])
def inserisci_amministratore():
    if 'user' not in session:
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autenticato'
        }),401

    if session['Ruolo'] != 'Amministratore':
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autorizzato'
        }),403

    data = request.get_json(silent=True)
    esito,messaggio = valida_body_richiesta(data,['username','password'])

    if not esito:
        return jsonify({
            'esito':'errore',
            'messaggio': messaggio
        }),400

    ### Verifichiamo che il valore di username sia valido ossia
    ### che non esiste gia nel db

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT Id FROM Utenti
        WHERE Username = ?
    ''',(data['username'],))

    if cursor.fetchone():
        cursor.close()
        conn.close()

        return jsonify({
            'esito':'errore',
            'messaggio':'Username non valido perchè gia presente'
        }),400

    cursor.execute('''
        INSERT INTO Utenti(Username,Password,Ruolo)
        VALUES (?,?,?)
    ''',(data['username'],data['password'],'Amministratore'))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'esito':'successo',
        'messaggio':'Inserimento utente amministratore avvenuto con successo'
    }),201

@app.route('/api/registrazione',methods=['POST'])
def registrazione():
    data = request.get_json(silent=True)
    esito,messaggio = valida_body_richiesta(data,['username','password'])

    if not esito:
        return jsonify({
            'esito':'errore',
            'messaggio': messaggio
        }),400

    ### Verifichiamo che il valore di username sia valido ossia
    ### che non esiste gia nel db

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT Id FROM Utenti
        WHERE Username = ?
    ''',(data['username'],))

    if cursor.fetchone():
        cursor.close()
        conn.close()

        return jsonify({
            'esito':'errore',
            'messaggio':'Username non valido perchè gia presente'
        }),400

    cursor.execute('''
        INSERT INTO Utenti(Username,Password,Ruolo)
        VALUES (?,?,?)
    ''',(data['username'],data['password'],'Cliente'))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'esito':'successo',
        'messaggio':'Registrazione avvenuta con successo'
    }),201

@app.route('/api/login',methods=['POST'])
def login():
    data = request.get_json(silent=True)
    esito , messaggio = valida_body_richiesta(data,['username','password'])

    if not esito:
        return jsonify({
            'esito':'errore',
            'messaggio': messaggio
        }),400

    username = data['username']
    password = data['password']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT Id, Ruolo FROM Utenti
        WHERE Username = ? AND Password = ?
    ''',(username,password))

    res = cursor.fetchone()
    if not res:
        cursor.close()
        conn.close()
        return jsonify({
            'esito':'errore',
            'messaggio':'Credenziali non valide'
        }),400

    session.permanent = True
    session['user'] = username
    session['id'] = res['Id']
    session['Ruolo'] = res['Ruolo']

    return jsonify({
        'esito':'successo',
        'messaggio':'Login effettuato con successo'
    }),200

@app.route('/api/logout',methods=['POST'])
def logout():
    if not 'user' in session:
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autenticato'
        }),401

    session.clear()
    return jsonify({
        'esito':'successo',
        'messaggio':'Logout effettuato con successo'
    }),200

@app.route('/api/prestito',methods=['POST'])
def richiedi_prestito():
    if 'user' not in session:
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autenticato'
        }),401

    if session['Ruolo'] != 'Cliente':
        return jsonify({
            'esito':'errore',
            'messaggio':'Non puoi richiedere un prestito da amministratore'
        }),403

    data = request.get_json(silent=True)
    esito, messaggio = valida_body_richiesta(data,['IdLibro'])

    ### Validazione valore IdLibro
    conn = get_db_connection()
    cursor = conn.cursor()

    ### verifico se l'utente ha acnora prestiti disponibili
    cursor.execute('''
        SELECT count(*) AS Conteggio FROM Prestiti
        WHERE IdUtente = ?
    ''',(session['id'],))

    conteggio = cursor.fetchone()['Conteggio']
    if conteggio >=10:
        cursor.close()
        conn.close()
        return jsonify({
            'esito':'errore',
            'messaggio':f'Impossibile procedere con il prestito, hai gia {conteggio} prestiti attivi'
        }),409

    ### Libro esiste?
    cursor.execute('''
        SELECT Disponibilità FROM Libri
        WHERE Id = ?
    ''',(data['IdLibro'],))

    res = cursor.fetchone()
    if not res:
        cursor.close()
        conn.close()
        return jsonify({
            'esito':'errore',
            'messaggio':'Valore IdLibro non valido'
        }),404

    ### Libro è disponibile?
    if res['Disponibilità'] == 0:
        cursor.close()
        conn.close()
        return jsonify({
            'esito':'errore',
            'messaggio':'Libro attualmente non disponibile per il prestito'
        }),409


    istante_attuale = datetime.now()
    data_inizio = istante_attuale.strftime('%Y-%m-%d')
    data_fine = (istante_attuale + timedelta(days=30)).strftime('%Y-%m-%d')

    ### INSERISCO RECORD PRESTITO
    cursor.execute('''
        INSERT INTO Prestiti (IdUtente,IdLibro,DataInizioPrestito,DataFinePrestito,Rinnovato)
        VALUES (?,?,?,?,?)
    ''',(session['id'],data['IdLibro'],data_inizio,data_fine,0))

    ### AGGIORNO LA DISPONIBILITÀ DEL LIBRO
    cursor.execute('''
        UPDATE Libri SET Disponibilità = 0
        WHERE Id = ?
    ''',(data['IdLibro'],))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'esito':'successo',
        'messaggio':'Richiesta di prestito elaborata con successo'
    }),200

@app.route('/api/visualizza_libri', methods=['GET'])
def visualizza_libri():
    if 'user' not in session:
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autenticato'
        }),401

    categoria = request.args.get('categoria')
    conn = get_db_connection()
    cursor = conn.cursor()

    if categoria == None:
        cursor.execute('''
            SELECT L.Titolo, L.Autore , L.AnnoPubblicazione, L.Disponibilità AS Stato, C.Categoria
            FROM Libri AS L JOIN Categorie AS C ON L.Categoria = C.Id
        ''')

        libri = [dict(riga) for riga in cursor.fetchall()]
    else:
        cursor.execute('''
            SELECT Id FROM Categorie
            WHERE Nome = ?
        ''',(categoria,))

        res = cursor.fetchone()
        if res == None:
            cursor.close()
            conn.close()

            return jsonify({
                'esito':'errore',
                'messaggio':'Valore di categoria non valido'
            }),404

        cursor.execute('''
            SELECT Titolo, Autore , AnnoPubblicazione, Disponibilità AS Stato
            FROM Libri WHERE Categoria = ?
        ''',(res['Id'],))

        libri = [dict(riga) for riga in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify({
        'esito':'successo',
        'libri': libri
    }),200

@app.route('/api/visualizza_prestiti',methods=['GET'])
def visualizza_prestiti():
    if 'user' not in session:
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autenticato'
        }),401

    if session['Ruolo'] != 'Cliente':
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autorizzato'
        }),403

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT P.Id, L.Titolo, L.Autore, P.DataInizioPrestito, P.DataFinePrestito, p.Rinnovato
        FROM Prestiti AS P JOIN Libri AS L ON P.IdLibro = L.Id
        WHERE P.IdUtente = ?
    ''',(session['id'],))

    prestiti = [dict(prestito) for prestito in cursor.fetchall()]
    cursor.close()
    conn.close()

    return jsonify({
        'esito':'successo',
        'prestiti': prestiti
    }),200

@app.route('/api/rinnova_prestito',methods=['POST'])
def rinnova_prestito():
    if 'user' not in session:
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autenticato'
        }),401

    if session['Ruolo'] != 'Cliente':
        return jsonify({
            'esito':'errore',
            'messaggio':'Utente non autorizzato'
        }),403

    data = request.get_json(silent=True)
    esito,messaggio = valida_body_richiesta(data,['IdPrestito'])

    if not esito:
        return jsonify({
            'esito':'errore',
            'messaggio': messaggio
        }),400

    ## Verifichiamo che esista un prestito con questo id
    ## e che sia riferito all'utente che ha effettuato la richiesta

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT IdUtente,Rinnovato FROM Prestiti
        WHERE Id = ?
    ''',(data['IdPrestito'],))

    res = cursor.fetchone()
    if res == None:
        cursor.close()
        conn.close()

        return jsonify({
            'esito':'errore',
            'messaggio':f'Nessun prestito presente avente id {data['IdPrestito']}'
        }),404

    if res['IdUtente'] != session['id']:
        cursor.close()
        conn.close()

        return jsonify({
            'esito':'errore',
            'messaggio':'Non sei autorizzato a rinnovare il prestito'
        }),403

    if res['Rinnovato']:
        cursor.close()
        conn.close()

        return jsonify({
            'esito':'errore',
            'messaggio':'Non è possibile rinnovare un prestito più di una volta'
        }),409

    nuova_scadenza = (datetime.now()+timedelta(days=15)).strftime('%Y-%m-%d')
    cursor.execute('''
        UPDATE Prestiti
        SET Rinnovato = 1, DataFinePrestito = ?
        WHERE Id = ?
    ''',(nuova_scadenza,data['IdPrestito']))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({
        'esito':'successo',
        'messaggio':'Prestito rinnovato con successo'
    }),200
