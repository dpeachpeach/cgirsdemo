       IDENTIFICATION DIVISION.
       PROGRAM-ID. PENCALC.
      *****************************************************************
      *    FAILURE TO FILE / FAILURE TO PAY - IRC 6651                *
      *    STEP 050.  FTF 5 PCT PER MONTH CAPPED AT 25 PCT.           *
      *    FTP 1/2 PCT PER MONTH.  FTF IS REDUCED BY FTP FOR ANY      *
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
       01  UPD                     PIC S9(11)V99 COMP-3.
       01  FTFA                    PIC S9(9)V99 COMP-3.
       01  FTPA                    PIC S9(9)V99 COMP-3.
       01  MINP                    PIC S9(9)V99 COMP-3.
       01  MOL                     PIC S9(3) COMP.
       01  DLD                     PIC S9(5) COMP.
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
           MOVE ZERO TO FTFA
           MOVE ZERO TO FTPA
           MOVE ZERO TO MINP
           MOVE ZERO TO MOL
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT < MKEY
               PERFORM 8100-RDTRN
           END-PERFORM
           PERFORM UNTIL TEOF = "Y" OR TKEY NOT = MKEY
               IF TRN-TC = 150
                   MOVE TRN-DT TO D150
               END-IF
               PERFORM 8100-RDTRN
           END-PERFORM
           COMPUTE UPD = BMF-ASSD - BMF-DEP - BMF-CRD
           IF UPD < ZERO
               MOVE ZERO TO UPD
           END-IF
           PERFORM 2200-MONTHS THRU 2200-X
           IF MOL > ZERO AND UPD > ZERO
               PERFORM 2300-FTF
               PERFORM 2400-FTP
               PERFORM 2500-OFFSET
               PERFORM 2600-MIN
               MOVE FTFA TO BMF-PFTF
               MOVE FTPA TO BMF-PFTP
               ADD 1 TO Q3
               MOVE BMF-EIN TO PR-EIN
               MOVE BMF-MFT TO PR-MFT
               MOVE BMF-TXPD TO PR-TXPD
               MOVE "P501" TO PR-COD
               MOVE "FTF/FTP ASSESSED" TO PR-TXT
               MOVE MOL TO PR-MO
               MOVE FTFA TO PR-FTF
               MOVE FTPA TO PR-FTP
               WRITE PNRPT-REC FROM PRPT
           END-IF.
      *
      *    DELINQUENCY IN MONTHS OR FRACTION THEREOF, RETURN DUE DATE
      *    TO THE POSTING DATE OF THE TC 150.
      *
       2200-MONTHS.
           IF D150 = ZERO
               MOVE ZERO TO MOL
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
           COMPUTE DLD = IG - IR
           IF DLD < 1
               MOVE ZERO TO MOL
           ELSE
               COMPUTE MOL = (DLD / 30) + 1
           END-IF.
       2200-X.
           EXIT.
      *
      *    FTF 5 PCT PER MONTH, MAXIMUM 25 PCT.
      *
       2300-FTF.
           COMPUTE FTFA = UPD * 0.05 * MOL
           IF FTFA > (UPD * 0.25)
               COMPUTE FTFA = UPD * 0.25
           END-IF.
      *
      *    FTP 1/2 PCT PER MONTH, MAXIMUM 25 PCT.
      *
       2400-FTP.
           COMPUTE FTPA = UPD * 0.005 * MOL
           IF FTPA > (UPD * 0.25)
               COMPUTE FTPA = UPD * 0.25
           END-IF.
      *
      *    IRC 6651(C)(1).  FTF IS REDUCED BY THE FTP FOR ANY MONTH
      *    IN WHICH BOTH PENALTIES APPLY.
      *
       2500-OFFSET.
           IF FTPA > ZERO
               COMPUTE FTFA = FTFA - FTPA
               IF FTFA < ZERO
                   MOVE ZERO TO FTFA
               END-IF
           END-IF.
      *
      *    IRM 20.1.2.3.7.4 MINIMUM PENALTY.  RETURN MORE THAN 60 DAYS
      *    LATE AND COMPUTED FTF BELOW THE FLOOR.  THE FLOOR IS THE
      *    LESSER OF THE TABLE AMOUNT OR 100 PCT OF THE UNPAID TAX.
      *    THE FLOOR IS NOT REDUCED BY THE FTP.
      *
       2600-MIN.
           IF DLD > 60
               MOVE 485.00 TO MINP
               IF UPD < MINP
                   MOVE UPD TO MINP
               END-IF
               IF FTFA < MINP
                   MOVE MINP TO FTFA
                   ADD 1 TO Q4
                   MOVE BMF-EIN TO PR-EIN
                   MOVE BMF-MFT TO PR-MFT
                   MOVE BMF-TXPD TO PR-TXPD
                   MOVE "P502" TO PR-COD
                   MOVE "MINIMUM FTF APPLIED" TO PR-TXT
                   MOVE MOL TO PR-MO
                   MOVE FTFA TO PR-FTF
                   MOVE FTPA TO PR-FTP
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
