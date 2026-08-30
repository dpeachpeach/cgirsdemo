       IDENTIFICATION DIVISION.
       PROGRAM-ID. BLDFIX.
      *****************************************************************
      *    CARD-TO-TAPE LOAD. CONVERTS UNPACKED FIXTURE TEXT TO       *
      *    PACKED MASTER FILE FORMAT. NOT PART OF THE NIGHTLY CYCLE.  *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODTXT ASSIGN TO "data/MODMAST.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT ENTTXT ASSIGN TO "data/ENTMAST.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT TRNTXT ASSIGN TO "data/TRANIN.txt"
               ORGANIZATION IS LINE SEQUENTIAL.
           SELECT MODOUT ASSIGN TO "data/BMFMOD.dat"
               ORGANIZATION IS SEQUENTIAL.
           SELECT ENTOUT ASSIGN TO "data/ENTMAST.dat"
               ORGANIZATION IS SEQUENTIAL.
           SELECT TRNOUT ASSIGN TO "data/TRANIN.dat"
               ORGANIZATION IS SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODTXT.
       01  MODTXT-REC              PIC X(181).
       FD  ENTTXT.
       01  ENTTXT-REC              PIC X(150).
       FD  TRNTXT.
       01  TRNTXT-REC              PIC X(60).
       FD  MODOUT
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  ENTOUT
           RECORD CONTAINS 150 CHARACTERS.
       COPY ENTREC.
       FD  TRNOUT
           RECORD CONTAINS 80 CHARACTERS.
       COPY TRANREC.
       WORKING-STORAGE SECTION.
       01  W-EOF                   PIC X VALUE "N".
       01  W-CNT                   PIC 9(5) VALUE ZERO.
       01  W-TOT                   PIC 9(5) VALUE ZERO.
       01  TXTM.
           05  TM-EIN              PIC 9(09).
           05  TM-MFT              PIC 9(02).
           05  TM-TXPD             PIC 9(06).
           05  TM-NCTL             PIC X(04).
           05  TM-NAME             PIC X(35).
           05  TM-FSC              PIC X(01).
           05  TM-SIC              PIC X(01).
           05  TM-FRZ              PIC X(08).
           05  TM-ASED             PIC 9(07).
           05  TM-RSED             PIC 9(07).
           05  TM-CSED             PIC 9(07).
           05  TM-ASSD             PIC 9(11)V99.
           05  TM-DEP              PIC 9(11)V99.
           05  TM-CRD              PIC 9(11)V99.
           05  TM-PFTD             PIC 9(09)V99.
           05  TM-PFTF             PIC 9(09)V99.
           05  TM-PFTP             PIC 9(09)V99.
           05  TM-INT              PIC 9(09)V99.
           05  TM-W8               PIC X(08).
           05  TM-TCCNT            PIC 9(03).
       01  TXTT.
           05  TT-EIN              PIC 9(09).
           05  TT-MFT              PIC 9(02).
           05  TT-TXPD             PIC 9(06).
           05  TT-TC               PIC 9(03).
           05  TT-DT               PIC 9(07).
           05  TT-AMT              PIC 9(11)V99.
           05  TT-CYC              PIC 9(06).
           05  TT-DLN              PIC X(14).
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-MOD
           PERFORM 2000-ENT
           PERFORM 3000-TRN
           DISPLAY "BLDFIX TOTAL RECORDS " W-TOT
           STOP RUN.
       1000-MOD.
           OPEN INPUT MODTXT OUTPUT MODOUT
           MOVE "N" TO W-EOF
           MOVE ZERO TO W-CNT
           PERFORM UNTIL W-EOF = "Y"
               READ MODTXT INTO TXTM
                   AT END MOVE "Y" TO W-EOF
                   NOT AT END
                       PERFORM 1100-FMT
                       WRITE BMF-MOD-REC
                       ADD 1 TO W-CNT
               END-READ
           END-PERFORM
           CLOSE MODTXT MODOUT
           DISPLAY "  BMFMOD  " W-CNT
           ADD W-CNT TO W-TOT.
       1100-FMT.
           MOVE TM-EIN   TO BMF-EIN
           MOVE TM-MFT   TO BMF-MFT
           MOVE TM-TXPD  TO BMF-TXPD
           MOVE TM-NCTL  TO BMF-NCTL
           MOVE TM-NAME  TO BMF-NAME
           MOVE TM-FSC   TO BMF-FSC
           MOVE TM-SIC   TO BMF-SIC
           MOVE TM-FRZ   TO BMF-FRZ
           MOVE TM-ASED  TO BMF-ASED
           MOVE TM-RSED  TO BMF-RSED
           MOVE TM-CSED  TO BMF-CSED
           MOVE TM-ASSD  TO BMF-ASSD
           MOVE TM-DEP   TO BMF-DEP
           MOVE TM-CRD   TO BMF-CRD
           MOVE TM-PFTD  TO BMF-PFTD
           MOVE TM-PFTF  TO BMF-PFTF
           MOVE TM-PFTP  TO BMF-PFTP
           MOVE TM-INT   TO BMF-INT
           MOVE TM-W8    TO BMF-W8
           MOVE TM-TCCNT TO BMF-TCCNT
           MOVE SPACES   TO BMF-FILL.
       2000-ENT.
           OPEN INPUT ENTTXT OUTPUT ENTOUT
           MOVE "N" TO W-EOF
           MOVE ZERO TO W-CNT
           PERFORM UNTIL W-EOF = "Y"
               READ ENTTXT INTO ENT-REC
                   AT END MOVE "Y" TO W-EOF
                   NOT AT END
                       WRITE ENT-REC
                       ADD 1 TO W-CNT
               END-READ
           END-PERFORM
           CLOSE ENTTXT ENTOUT
           DISPLAY "  ENTMAST " W-CNT
           ADD W-CNT TO W-TOT.
       3000-TRN.
           OPEN INPUT TRNTXT OUTPUT TRNOUT
           MOVE "N" TO W-EOF
           MOVE ZERO TO W-CNT
           PERFORM UNTIL W-EOF = "Y"
               READ TRNTXT INTO TXTT
                   AT END MOVE "Y" TO W-EOF
                   NOT AT END
                       MOVE TT-EIN  TO TRN-EIN
                       MOVE TT-MFT  TO TRN-MFT
                       MOVE TT-TXPD TO TRN-TXPD
                       MOVE TT-TC   TO TRN-TC
                       MOVE TT-DT   TO TRN-DT
                       MOVE TT-AMT  TO TRN-AMT
                       MOVE TT-CYC  TO TRN-CYC
                       MOVE TT-DLN  TO TRN-DLN
                       MOVE SPACES  TO TRN-FILL
                       WRITE TRN-REC
                       ADD 1 TO W-CNT
               END-READ
           END-PERFORM
           CLOSE TRNTXT TRNOUT
           DISPLAY "  TRANIN  " W-CNT
           ADD W-CNT TO W-TOT.
