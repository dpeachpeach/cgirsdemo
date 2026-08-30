      *****************************************************************
      *    NOTICE OUTPUT RECORD           RECFM=FB  LRECL=00100       *
      *****************************************************************
       01  NOT-REC.
           05  NOT-EIN                 PIC 9(09).
           05  NOT-MFT                 PIC 9(02).
           05  NOT-TXPD                PIC 9(06).
           05  NOT-CP                  PIC X(04).
           05  NOT-NCTL                PIC X(04).
           05  NOT-NAME                PIC X(35).
           05  NOT-AMT                 PIC S9(11)V99 COMP-3.
           05  NOT-DT                  PIC 9(07).
           05  NOT-SEV                 PIC X(01).
           05  NOT-FILL                PIC X(25).
