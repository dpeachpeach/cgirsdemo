       IDENTIFICATION DIVISION.
       PROGRAM-ID. PENCALC.
      *****************************************************************
      *    FAILURE TO FILE / FAILURE TO PAY - IRC 6651                *
      *    STEP 050.  FTF 5 PCT PER MONTH CAPPED AT 25 PCT.           *
      *    FTP 1/2 PCT PER MONTH.  FTF IS REDUCED BY FTP FOR ANY      *
      *    MINIMUM PENALTY FLOOR LAST UPLIFTED 01/16 - SEE RUN BOOK   *
      *    MONTH IN WHICH BOTH APPLY - IRC 6651(C)(1).                *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODFTD.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT TRNIN  ASSIGN TO "data/TRANIN.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT MODOT  ASSIGN TO "data/MODPEN.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS3.
           SELECT PNRPT  ASSIGN TO "data/PENCALC.rpt"
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
       FD  PNRPT.
       01  PNRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  FS3                     PIC XX VALUE "00".
       01  MEOF                    PIC X VALUE "N".
       01  TEOF                    PIC X VALUE "N".
       01  Q1                      PIC 9(6) VALUE ZERO.
       01  Q2                      PIC 9(6) VALUE ZERO.
       01  Q3                      PIC 9(6) VALUE ZERO.
       01  Q4                      PIC 9(6) VALUE ZERO.
       01  MKEY                    PIC X(17).
       01  TKEY                    PIC X(17).
       01  D150                    PIC 9(7).
       01  WUPD                     PIC S9(11)V99 COMP-3.
       01  WF51                    PIC S9(9)V99 COMP-3.
       01  WF52                    PIC S9(9)V99 COMP-3.
       01  WMIN                    PIC S9(9)V99 COMP-3.
       01  WMOL                     PIC S9(3) COMP.
       01  WDLD                     PIC S9(5) COMP.
       01  GG                      PIC 9(8).
       01  GR                      PIC 9(8).
       01  IG                      PIC S9(9) COMP.
       01  IR                      PIC S9(9) COMP.
       01  VY                      PIC 9(4).
       01  VM                      PIC 9(2).
       01  DC-PARM.
           05  DCP-FUNC            PIC X(01).
           05  DCP-GREG            PIC 9(08).
           05  DCP-JUL             PIC 9(07).
           05  DCP-RC              PIC X(01).
           05  DCP-RSV             PIC X(07).
       01  PRPT.
           05  FILLER              PIC X(07) VALUE "PENCALC".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  PR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  PR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  PR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  PR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  PR-TXT              PIC X(24).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  PR-MO               PIC ZZ9.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  PR-FTF              PIC ZZZZZZ9.99.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  PR-FTP              PIC ZZZZZZ9.99.
           05  FILLER              PIC X(30) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN TRNIN OUTPUT MODOT PNRPT
           PERFORM 8100-RDTRN
           PERFORM 2000-DRIVE UNTIL MEOF = "Y"
           CLOSE MODIN TRNIN MODOT PNRPT
           DISPLAY "PENCALC READ    " Q1
           DISPLAY "PENCALC WRITTEN " Q2
           DISPLAY "PENCALC FTF     " Q3
           DISPLAY "PENCALC MINIMUM " Q4
           STOP RUN.
       2000-DRIVE.
           READ MODIN
               AT END
                   MOVE "Y" TO MEOF
               NOT AT END
                   ADD 1 TO Q1
                   PERFORM 2100-PEN
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO Q2
           END-READ.
       2100-PEN.
           MOVE BMF-KEY TO MKEY
           MOVE ZERO TO D150
           MOVE ZERO TO WF51
           MOVE ZERO TO WF52
           MOVE ZERO TO WMIN
           MOVE ZERO TO WMOL
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT < MKEY
               PERFORM 8100-RDTRN
           END-PERFORM
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT = MKEY
               IF TRN-TC = 150
                   MOVE TRN-DT TO D150
               END-IF
               PERFORM 8100-RDTRN
           END-PERFORM
           COMPUTE WUPD = BMF-ASSD - BMF-DEP - BMF-CRD
           IF WUPD < ZERO
               MOVE ZERO TO WUPD
           END-IF
           PERFORM 2200-MONTHS THRU 2200-X
           IF WMOL > ZERO AND WUPD > ZERO
               PERFORM 2300-FTF
               PERFORM 2400-FTP
               PERFORM 2500-OFFSET
               PERFORM 2600-MIN
               MOVE WF51 TO BMF-PFTF
               MOVE WF52 TO BMF-PFTP
               ADD 1 TO Q3
               MOVE BMF-EIN TO PR-EIN
               MOVE BMF-MFT TO PR-MFT
               MOVE BMF-TXPD TO PR-TXPD
               MOVE "P501" TO PR-COD
               MOVE "FTF/FTP ASSESSED" TO PR-TXT
               MOVE WMOL TO PR-MO
               MOVE WF51 TO PR-FTF
               MOVE WF52 TO PR-FTP
               WRITE PNRPT-REC FROM PRPT
           END-IF.
       2200-MONTHS.
           IF D150 = ZERO
               MOVE ZERO TO WMOL
               GO TO 2200-X
           END-IF
           MOVE BMF-TXPD(1:4) TO VY
           MOVE BMF-TXPD(5:2) TO VM
           ADD 1 TO VM
           IF VM > 12
               SUBTRACT 12 FROM VM
               ADD 1 TO VY
           END-IF
           COMPUTE GR = VY * 10000 + VM * 100 + 15
           MOVE "G" TO DCP-FUNC
           MOVE D150 TO DCP-JUL
           MOVE ZERO TO DCP-GREG
           CALL "DATCNV" USING DC-PARM
           MOVE DCP-GREG TO GG
           COMPUTE IG = FUNCTION INTEGER-OF-DATE(GG)
           COMPUTE IR = FUNCTION INTEGER-OF-DATE(GR)
           COMPUTE WDLD = IG - IR
           IF WDLD < 1
               MOVE ZERO TO WMOL
           ELSE
               COMPUTE WMOL = (WDLD / 30) + 1
           END-IF.
       2200-X.
           EXIT.
       2300-FTF.
           COMPUTE WF51 = WUPD * 0.05 * WMOL
           IF WF51 > (WUPD * 0.25)
               COMPUTE WF51 = WUPD * 0.25
           END-IF.
       2400-FTP.
           COMPUTE WF52 = WUPD * 0.005 * WMOL
           IF WF52 > (WUPD * 0.25)
               COMPUTE WF52 = WUPD * 0.25
           END-IF.
       2500-OFFSET.
           IF WF52 > ZERO
               COMPUTE WF51 = WF51 - WF52
               IF WF51 < ZERO
                   MOVE ZERO TO WF51
               END-IF
           END-IF.
       2600-MIN.
           IF WDLD > 60
               MOVE 485.00 TO WMIN
               IF WUPD < WMIN
                   MOVE WUPD TO WMIN
               END-IF
               IF WF51 < WMIN
                   MOVE WMIN TO WF51
                   ADD 1 TO Q4
                   MOVE BMF-EIN TO PR-EIN
                   MOVE BMF-MFT TO PR-MFT
                   MOVE BMF-TXPD TO PR-TXPD
                   MOVE "P502" TO PR-COD
                   MOVE "MINIMUM FTF APPLIED" TO PR-TXT
                   MOVE WMOL TO PR-MO
                   MOVE WF51 TO PR-FTF
                   MOVE WF52 TO PR-FTP
                   WRITE PNRPT-REC FROM PRPT
               END-IF
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
