       IDENTIFICATION DIVISION.
       PROGRAM-ID. NOTGEN.
      *****************************************************************
      *    NOTICE SELECTION AND GENERATION                            *
      *    STEP 110.  LAST STEP OF THE CYCLE.  READS THE SETTLED      *
      *    MODULE AND WRITES CP NOTICE RECORDS.  A REFUND FREEZE      *
      *    SUPPRESSES THE NOTICE BUT NOT THE ANALYSIS.                *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODOFF.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT NOTOT  ASSIGN TO "data/NOTICE.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT NGRPT  ASSIGN TO "data/NOTGEN.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  NOTOT
           RECORD CONTAINS 100 CHARACTERS.
       COPY NOTREC.
       FD  NGRPT.
       01  NGRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  K1                      PIC 9(6) VALUE ZERO.
       01  K2                      PIC 9(6) VALUE ZERO.
       01  K3                      PIC 9(6) VALUE ZERO.
       01  BAL                     PIC S9(11)V99 COMP-3.
       01  LIA                     PIC S9(11)V99 COMP-3.
       01  CPC                     PIC X(4).
       01  SEV                     PIC X.
       01  SUPSW                   PIC X.
       01  DV-PARM.
           05  DVP-FUNC            PIC X(01).
           05  DVP-GREG            PIC 9(08).
           05  DVP-JUL             PIC 9(07).
           05  DVP-DOW             PIC 9(01).
           05  DVP-RC              PIC X(01).
           05  DVP-RSV             PIC X(06).
       01  NRPT.
           05  FILLER              PIC X(06) VALUE "NOTGEN".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  NR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  NR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  NR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  NR-CP               PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  NR-TXT              PIC X(28).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  NR-AMT              PIC ZZZZZZZZ9.99-.
           05  FILLER              PIC X(02) VALUE SPACES.
           05  NR-SEV              PIC X(01).
           05  FILLER              PIC X(30) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN OUTPUT NOTOT NGRPT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           CLOSE MODIN NOTOT NGRPT
           DISPLAY "NOTGEN  READ    " K1
           DISPLAY "NOTGEN  NOTICES " K2
           DISPLAY "NOTGEN  SUPPRESS" K3
           STOP RUN.
       2000-PROC.
           READ MODIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO K1
                   PERFORM 2100-SEL THRU 2100-X
           END-READ.
       2100-SEL.
           MOVE SPACES TO CPC
           MOVE " " TO SEV
           MOVE "N" TO SUPSW
           COMPUTE LIA = BMF-ASSD + BMF-PFTD + BMF-PFTF + BMF-PFTP
           COMPUTE BAL = LIA - BMF-DEP - BMF-CRD - BMF-INT
      *
      *    SELECTION IS IN PRIORITY ORDER.  THE FIRST CONDITION THAT
      *    APPLIES OWNS THE MODULE FOR THIS CYCLE.
      *
           EVALUATE TRUE
               WHEN BMF-FRZ-A = "A"
                   MOVE "0193" TO CPC
                   MOVE "3" TO SEV
               WHEN BMF-PFTD > ZERO
                   MOVE "0194" TO CPC
                   MOVE "2" TO SEV
               WHEN BMF-PFTF > ZERO
                   MOVE "0215" TO CPC
                   MOVE "2" TO SEV
               WHEN BAL > 100
                   MOVE "0161" TO CPC
                   MOVE "1" TO SEV
               WHEN BAL < -100
                   MOVE "0267" TO CPC
                   MOVE "1" TO SEV
               WHEN OTHER
                   GO TO 2100-X
           END-EVALUATE
      *
      *    A REFUND FREEZE STOPS THE OVERPAYMENT NOTICE ONLY.
      *
           IF CPC = "0267" AND BMF-FRZ-R = "R"
               MOVE "Y" TO SUPSW
           END-IF
           IF BMF-FRZ-Z = "Z"
               MOVE "Y" TO SUPSW
           END-IF
           MOVE BMF-EIN TO NR-EIN
           MOVE BMF-MFT TO NR-MFT
           MOVE BMF-TXPD TO NR-TXPD
           MOVE CPC TO NR-CP
           MOVE BAL TO NR-AMT
           MOVE SEV TO NR-SEV
           IF SUPSW = "Y"
               ADD 1 TO K3
               MOVE "SUPPRESSED BY FREEZE" TO NR-TXT
               WRITE NGRPT-REC FROM NRPT
               GO TO 2100-X
           END-IF
           PERFORM 2200-BLD
           WRITE NOT-REC
           ADD 1 TO K2
           EVALUATE CPC
               WHEN "0193"
                   MOVE "DUPLICATE RETURN FILED" TO NR-TXT
               WHEN "0194"
                   MOVE "POSSIBLE FTD PENALTY" TO NR-TXT
               WHEN "0215"
                   MOVE "CIVIL PENALTY ASSESSED" TO NR-TXT
               WHEN "0161"
                   MOVE "BALANCE DUE" TO NR-TXT
               WHEN OTHER
                   MOVE "OVERPAYMENT - REFUND DUE" TO NR-TXT
           END-EVALUATE
           WRITE NGRPT-REC FROM NRPT.
       2100-X.
           EXIT.
       2200-BLD.
           MOVE BMF-EIN TO NOT-EIN
           MOVE BMF-MFT TO NOT-MFT
           MOVE BMF-TXPD TO NOT-TXPD
           MOVE CPC TO NOT-CP
           MOVE BMF-NCTL TO NOT-NCTL
           MOVE BMF-NAME TO NOT-NAME
           MOVE BAL TO NOT-AMT
           MOVE SEV TO NOT-SEV
           MOVE SPACES TO NOT-FILL
           MOVE 20260815 TO DVP-GREG
           MOVE "B" TO DVP-FUNC
           CALL "DATECNV" USING DV-PARM
           MOVE DVP-JUL TO NOT-DT.
