      *****************************************************************
      *    TRANSACTION RECORD             RECFM=FB  LRECL=00080       *
      *****************************************************************
       01  TRN-REC.
           05  TRN-EIN                 PIC 9(09).
           05  TRN-MFT                 PIC 9(02).
           05  TRN-TXPD                PIC 9(06).
           05  TRN-TC                  PIC 9(03).
           05  TRN-DT                  PIC 9(07).
           05  TRN-AMT                 PIC S9(11)V99 COMP-3.
           05  TRN-CYC                 PIC 9(06).
           05  TRN-DLN                 PIC X(14).
           05  TRN-FILL                PIC X(26).
