      *****************************************************************
      *    BMF ENTITY RECORD              RECFM=FB  LRECL=00150       *
      *****************************************************************
       01  ENT-REC.
           05  ENT-EIN                 PIC 9(09).
           05  ENT-NAME                PIC X(35).
           05  ENT-NCTL                PIC X(04).
           05  ENT-SORT                PIC X(04).
           05  ENT-ADDR                PIC X(35).
           05  ENT-CITY                PIC X(22).
           05  ENT-ST                  PIC X(02).
           05  ENT-ZIP                 PIC 9(09).
           05  ENT-FYM                 PIC 9(02).
           05  ENT-EC                  PIC X(01).
           05  ENT-IND.
               10  ENT-I-941           PIC X(01).
               10  ENT-I-940           PIC X(01).
               10  ENT-I-1120          PIC X(01).
               10  ENT-I-720           PIC X(01).
           05  ENT-XREF                PIC 9(09).
           05  ENT-FILL                PIC X(14).
