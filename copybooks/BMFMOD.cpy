      *****************************************************************
      *    BMF TAX MODULE RECORD          RECFM=FB  LRECL=00150       *
      *    REV 11/87  ADDED W8 AREA PER RCC-2214                      *
      *****************************************************************
       01  BMF-MOD-REC.
           05  BMF-KEY.
               10  BMF-EIN             PIC 9(09).
               10  BMF-MFT             PIC 9(02).
               10  BMF-TXPD            PIC 9(06).
           05  BMF-NCTL                PIC X(04).
           05  BMF-NAME                PIC X(35).
           05  BMF-FSC                 PIC X(01).
           05  BMF-SIC                 PIC X(01).
           05  BMF-FRZ.
               10  BMF-FRZ-A           PIC X(01).
               10  BMF-FRZ-V           PIC X(01).
               10  BMF-FRZ-L           PIC X(01).
               10  BMF-FRZ-R           PIC X(01).
               10  BMF-FRZ-S           PIC X(01).
               10  BMF-FRZ-X           PIC X(01).
               10  BMF-FRZ-Z           PIC X(01).
               10  BMF-FRZ-O           PIC X(01).
           05  BMF-ASED                PIC 9(07) COMP-3.
           05  BMF-RSED                PIC 9(07) COMP-3.
           05  BMF-CSED                PIC 9(07) COMP-3.
           05  BMF-ASSD                PIC S9(11)V99 COMP-3.
           05  BMF-DEP                 PIC S9(11)V99 COMP-3.
           05  BMF-CRD                 PIC S9(11)V99 COMP-3.
           05  BMF-PFTD                PIC S9(09)V99 COMP-3.
           05  BMF-PFTF                PIC S9(09)V99 COMP-3.
           05  BMF-PFTP                PIC S9(09)V99 COMP-3.
           05  BMF-INT                 PIC S9(09)V99 COMP-3.
           05  BMF-W8                  PIC X(08).
           05  BMF-TCCNT               PIC 9(03).
           05  BMF-FILL                PIC X(16).
