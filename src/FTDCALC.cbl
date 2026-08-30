       IDENTIFICATION DIVISION.
       PROGRAM-ID. FTDCALC.
      *****************************************************************
      *    FAILURE TO DEPOSIT PENALTY - IRC 6656                      *
      *    STEP 040.  CALLS PENACC FOR PACKED ACCUMULATION.           *
      *    FOUR TIER TIME SENSITIVE RATE STRUCTURE.                   *
      *    REV 09/93 SIC 2 HANDLING PER RCC-6120                      *
      *    RATES CARRIED IN LINE. LAST VERIFIED AGAINST IRM 20.1.4.7  *
      *    (2 / 5 / 10 PCT) 01/91. FOURTH TIER ADDED LATER BY PIC.    *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODSTAT.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT TRNIN  ASSIGN TO "data/TRANIN.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT MODOT  ASSIGN TO "data/MODFTD.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS3.
           SELECT FTRPT  ASSIGN TO "data/FTDCALC.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  TRNIN
           RECORD CONTAINS 80 CHARACTERS.
       COPY TRANREC.
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  FTRPT.
       01  FTRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  FS3                     PIC XX VALUE "00".
       01  MEOF                    PIC X VALUE "N".
       01  TEOF                    PIC X VALUE "N".
       01  R1                      PIC 9(6) VALUE ZERO.
       01  R2                      PIC 9(6) VALUE ZERO.
       01  R3                      PIC 9(6) VALUE ZERO.
       01  R4                      PIC 9(6) VALUE ZERO.
       01  R5                      PIC 9(6) VALUE ZERO.
       01  MKEY                    PIC X(17).
       01  TKEY                    PIC X(17).
       01  WNDP                    PIC 9(3).
       01  DL                      PIC S9(5) COMP.
       01  GD                      PIC 9(8).
       01  GU                      PIC 9(8).
       01  IDD                      PIC S9(9) COMP.
       01  IU                      PIC S9(9) COMP.
       01  UY                      PIC 9(4).
       01  UM                      PIC 9(2).
       01  UDY                     PIC 9(2).
       01  UJ                      PIC 9(7).
       01  WTOT                  PIC S9(11)V99 COMP-3.
       01  WSHT                   PIC S9(11)V99 COMP-3.
       01  WBYP                   PIC X.
       01  WPIC                   PIC X.
       01  WDFR                   PIC S9(11)V99 COMP-3.
       01  WDF1                   PIC 9(6) VALUE 202003.
       01  WDF2                   PIC 9(6) VALUE 202012.
       01  WDPC                   PIC S9(1)V9(4) VALUE 0.5000 COMP-3.
       01  DC-PARM.
           05  DCP-FUNC            PIC X(01).
           05  DCP-GREG            PIC 9(08).
           05  DCP-JUL             PIC 9(07).
           05  DCP-RC              PIC X(01).
           05  DCP-RSV             PIC X(07).
       01  PA-PARM.
           05  PA-BAS              PIC S9(11)V99 COMP-3.
           05  PA-RT               PIC S9(01)V9(04) COMP-3.
           05  PA-ACC              PIC S9(09)V99 COMP-3.
           05  PA-AMT              PIC S9(09)V99 COMP-3.
           05  PA-RC               PIC X(01).
           05  PA-RSV              PIC X(09).
       01  FRPT.
           05  FILLER              PIC X(07) VALUE "FTDCALC".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  FR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  FR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  FR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  FR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  FR-TXT              PIC X(26).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  FR-DL               PIC ZZZ9-.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  FR-TIER             PIC 9(01).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  FR-AMT              PIC ZZZZZZZ9.99.
           05  FILLER              PIC X(30) VALUE SPACES.
       COPY PENWORK.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN TRNIN OUTPUT MODOT FTRPT
           PERFORM 8100-RDTRN
           PERFORM 2000-DRIVE UNTIL MEOF = "Y"
           CLOSE MODIN TRNIN MODOT FTRPT
           DISPLAY "FTDCALC READ    " R1
           DISPLAY "FTDCALC WRITTEN " R2
           DISPLAY "FTDCALC PENALTY " R3
           DISPLAY "FTDCALC DEMINIM " R4
           DISPLAY "FTDCALC BYPASS  " R5
           STOP RUN.
       2000-DRIVE.
           READ MODIN
               AT END
                   MOVE "Y" TO MEOF
               NOT AT END
                   ADD 1 TO R1
                   PERFORM 3000-COMP
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO R2
           END-READ.
       3000-COMP.
           MOVE BMF-KEY TO MKEY
           MOVE ZERO TO PW-ACC
           MOVE ZERO TO PW-AMT
           MOVE ZERO TO PW-DLQ
           MOVE ZERO TO PW-TIER
           MOVE ZERO TO WNDP
           MOVE ZERO TO WTOT
           MOVE "N" TO WBYP
           MOVE "N" TO WPIC
           MOVE ZERO TO PA-ACC
           MOVE ZERO TO PA-AMT
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT < MKEY
               PERFORM 8100-RDTRN
           END-PERFORM
           IF BMF-FRZ-A = "A"
               MOVE "Y" TO WBYP
           END-IF
           IF BMF-FRZ-S = "S"
               MOVE "Y" TO WBYP
           END-IF
           MOVE BMF-TXPD(1:4) TO UY
           MOVE BMF-TXPD(5:2) TO UM
           ADD 1 TO UM
           IF UM > 12
               SUBTRACT 12 FROM UM
               ADD 1 TO UY
           END-IF
           MOVE 15 TO UDY
           IF BMF-SIC = "1"
               MOVE 03 TO UDY
           END-IF
           IF BMF-SIC = "2"
               MOVE 31 TO UDY
               MOVE 01 TO UM
               ADD 1 TO UY
           END-IF
           COMPUTE GU = UY * 10000 + UM * 100 + UDY
           COMPUTE IU = FUNCTION INTEGER-OF-DATE(GU)
           MOVE "J" TO DCP-FUNC
           MOVE GU TO DCP-GREG
           CALL "DATCNV" USING DC-PARM
           MOVE DCP-JUL TO UJ
           IF BMF-W8(3:1) = "X"
               MOVE "Y" TO WPIC
           END-IF
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT = MKEY
               IF TRN-TC = 650
                   ADD 1 TO WNDP
                   ADD TRN-AMT TO WTOT
                   MOVE "G" TO DCP-FUNC
                   MOVE TRN-DT TO DCP-JUL
                   MOVE ZERO TO DCP-GREG
                   CALL "DATCNV" USING DC-PARM
                   IF DCP-RC = "0"
                       MOVE DCP-GREG TO GD
                       COMPUTE IDD = FUNCTION INTEGER-OF-DATE(GD)
                       COMPUTE DL = IDD - IU
                   ELSE
                       MOVE ZERO TO DL
                   END-IF
                   IF DL > ZERO
                       IF DL > PW-DLQ
                           MOVE DL TO PW-DLQ
                       END-IF
                       EVALUATE TRUE
                           WHEN DL < 6
                               MOVE 1 TO PW-TIER
                               MOVE 0.0200 TO PW-RT
                           WHEN DL < 16
                               MOVE 2 TO PW-TIER
                               MOVE 0.0500 TO PW-RT
                           WHEN OTHER
                               MOVE 3 TO PW-TIER
                               MOVE 0.1000 TO PW-RT
                       END-EVALUATE
                       IF WPIC = "Y" AND DL > 15
                           MOVE 4 TO PW-TIER
                           MOVE 0.1500 TO PW-RT
                       END-IF
                       IF WBYP = "N" AND BMF-ASSD NOT < 2500
                           MOVE TRN-AMT TO PA-BAS
                           MOVE PW-RT TO PA-RT
                           CALL "PENACC" USING PA-PARM
                           ADD PA-AMT TO PW-ACC
                           MOVE BMF-EIN TO FR-EIN
                           MOVE BMF-MFT TO FR-MFT
                           MOVE BMF-TXPD TO FR-TXPD
                           MOVE "F401" TO FR-COD
                           MOVE "LATE DEPOSIT" TO FR-TXT
                           MOVE DL TO FR-DL
                           MOVE PW-TIER TO FR-TIER
                           MOVE PA-AMT TO FR-AMT
                           WRITE FTRPT-REC FROM FRPT
                       END-IF
                   END-IF
               END-IF
               PERFORM 8100-RDTRN
           END-PERFORM
           COMPUTE WSHT = BMF-ASSD - WTOT
           IF BMF-ASSD < 2500
               ADD 1 TO R4
               MOVE BMF-EIN TO FR-EIN
               MOVE BMF-MFT TO FR-MFT
               MOVE BMF-TXPD TO FR-TXPD
               MOVE "F402" TO FR-COD
               MOVE "DE MINIMIS - NO PENALTY" TO FR-TXT
               MOVE ZERO TO FR-DL
               MOVE ZERO TO FR-TIER
               MOVE ZERO TO FR-AMT
               WRITE FTRPT-REC FROM FRPT
               MOVE ZERO TO PW-ACC
           END-IF
      *
      *    DEFERRAL OF THE EMPLOYER SHARE.  APPLIES TO DEPOSITS DUE
      *    IN THE DEFERRAL WINDOW ONLY.  HALF WAS DUE 12/31/21 AND
      *    THE BALANCE 12/31/22.  NO CURRENT PERIOD QUALIFIES.
      *
           IF BMF-TXPD NOT < WDF1 AND BMF-TXPD NOT > WDF2
               COMPUTE WDFR = BMF-ASSD * WDPC
               IF WDFR > ZERO
                   SUBTRACT WDFR FROM PW-ACC
                   IF PW-ACC < ZERO
                       MOVE ZERO TO PW-ACC
                   END-IF
                   MOVE BMF-EIN TO FR-EIN
                   MOVE BMF-MFT TO FR-MFT
                   MOVE BMF-TXPD TO FR-TXPD
                   MOVE "F404" TO FR-COD
                   MOVE "DEFERRED - SEC 2302" TO FR-TXT
                   MOVE ZERO TO FR-DL
                   MOVE ZERO TO FR-TIER
                   MOVE WDFR TO FR-AMT
                   WRITE FTRPT-REC FROM FRPT
               END-IF
           END-IF
           IF WBYP = "Y"
               ADD 1 TO R5
               MOVE BMF-EIN TO FR-EIN
               MOVE BMF-MFT TO FR-MFT
               MOVE BMF-TXPD TO FR-TXPD
               MOVE "F403" TO FR-COD
               MOVE "FREEZE - PENALTY BYPASSED" TO FR-TXT
               MOVE ZERO TO FR-DL
               MOVE ZERO TO FR-TIER
               MOVE ZERO TO FR-AMT
               WRITE FTRPT-REC FROM FRPT
               MOVE ZERO TO PW-ACC
           END-IF
           IF PW-ACC > ZERO
               MOVE PW-ACC TO BMF-PFTD
               ADD 1 TO R3
           END-IF.
       8100-RDTRN.
           READ TRNIN
               AT END
                   MOVE "Y" TO TEOF
                   MOVE HIGH-VALUES TO TKEY
               NOT AT END
                   MOVE TRN-EIN  TO TKEY(1:9)
                   MOVE TRN-MFT  TO TKEY(10:2)
                   MOVE TRN-TXPD TO TKEY(12:6)
           END-READ.
