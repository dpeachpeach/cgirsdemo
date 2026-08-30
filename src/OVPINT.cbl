       IDENTIFICATION DIVISION.
       PROGRAM-ID. OVPINT.
      *****************************************************************
      *    OVERPAYMENT INTEREST - IRC 6611                            *
      *    STEP 080.  NO INTEREST WHEN THE REFUND IS SCHEDULED WITHIN *
      *    45 DAYS OF THE LATER OF THE DUE DATE OR THE DATE THE       *
      *    RETURN WAS FILED IN PROCESSIBLE FORM - IRC 6611(E).        *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT MODIN  ASSIGN TO "data/MODFRZ.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT MODOT  ASSIGN TO "data/MODINT.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT OIRPT  ASSIGN TO "data/OVPINT.rpt"
               ORGANIZATION IS LINE SEQUENTIAL.
       DATA DIVISION.
       FILE SECTION.
       FD  MODIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY BMFMOD.
       FD  MODOT
           RECORD CONTAINS 150 CHARACTERS.
       01  MODOT-REC               PIC X(150).
       FD  OIRPT.
       01  OIRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  N1                      PIC 9(6) VALUE ZERO.
       01  N2                      PIC 9(6) VALUE ZERO.
       01  N3                      PIC 9(6) VALUE ZERO.
       01  N4                      PIC 9(6) VALUE ZERO.
       01  CYCDT                   PIC 9(8) VALUE 20260815.
       01  WOVP                     PIC S9(11)V99 COMP-3.
       01  WLIA                     PIC S9(11)V99 COMP-3.
       01  WINT                    PIC S9(9)V99 COMP-3.
       01  WAVD                    PIC 9(8).
       01  IAV                     PIC S9(9) COMP.
       01  ICY                     PIC S9(9) COMP.
       01  WNDY                     PIC S9(5) COMP.
       01  WRT7                   PIC S9(1)V9(4) COMP-3.
       01  XY                      PIC 9(4).
       01  XM                      PIC 9(2).
       01  DV-PARM.
           05  DVP-FUNC            PIC X(01).
           05  DVP-GREG            PIC 9(08).
           05  DVP-JUL             PIC 9(07).
           05  DVP-DOW             PIC 9(01).
           05  DVP-RC              PIC X(01).
           05  DVP-RSV             PIC X(06).
       01  ORPT.
           05  FILLER              PIC X(06) VALUE "OVPINT".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  OR-EIN              PIC 9(09).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  OR-MFT              PIC 9(02).
           05  FILLER              PIC X(01) VALUE SPACES.
           05  OR-TXPD             PIC 9(06).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  OR-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  OR-TXT              PIC X(26).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  OR-OVP              PIC ZZZZZZZZ9.99.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  OR-DAYS             PIC ZZZ9.
           05  FILLER              PIC X(01) VALUE SPACES.
           05  OR-INT              PIC ZZZZZZ9.99.
           05  FILLER              PIC X(20) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           OPEN INPUT MODIN OUTPUT MODOT OIRPT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           CLOSE MODIN MODOT OIRPT
           DISPLAY "OVPINT  READ    " N1
           DISPLAY "OVPINT  WRITTEN " N2
           DISPLAY "OVPINT  INTEREST" N3
           DISPLAY "OVPINT  45 DAY  " N4
           STOP RUN.
       2000-PROC.
           READ MODIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO N1
                   PERFORM 2100-INT THRU 2100-X
                   WRITE MODOT-REC FROM BMF-MOD-REC
                   ADD 1 TO N2
           END-READ.
       2100-INT.
           MOVE ZERO TO WINT
           COMPUTE WLIA = BMF-ASSD + BMF-PFTD + BMF-PFTF + BMF-PFTP
           COMPUTE WOVP = BMF-DEP + BMF-CRD - WLIA
           IF WOVP NOT > ZERO
               GO TO 2100-X
           END-IF
           MOVE BMF-TXPD(1:4) TO XY
           MOVE BMF-TXPD(5:2) TO XM
           ADD 1 TO XM
           IF XM > 12
               SUBTRACT 12 FROM XM
               ADD 1 TO XY
           END-IF
           COMPUTE DVP-GREG = XY * 10000 + XM * 100 + 15
           MOVE "B" TO DVP-FUNC
           CALL "DATECNV" USING DV-PARM
           MOVE DVP-GREG TO WAVD
           COMPUTE IAV = FUNCTION INTEGER-OF-DATE(WAVD)
           COMPUTE ICY = FUNCTION INTEGER-OF-DATE(CYCDT)
           COMPUTE WNDY = ICY - IAV
           IF WNDY NOT > 45
               ADD 1 TO N4
               MOVE BMF-EIN TO OR-EIN
               MOVE BMF-MFT TO OR-MFT
               MOVE BMF-TXPD TO OR-TXPD
               MOVE "O801" TO OR-COD
               MOVE "45 DAY RULE - NO INTEREST" TO OR-TXT
               MOVE WOVP TO OR-OVP
               MOVE WNDY TO OR-DAYS
               MOVE ZERO TO OR-INT
               WRITE OIRPT-REC FROM ORPT
               GO TO 2100-X
           END-IF
           SUBTRACT 30 FROM WNDY
           IF WNDY NOT > ZERO
               GO TO 2100-X
           END-IF
           MOVE 0.0700 TO WRT7
           COMPUTE WINT ROUNDED = WOVP * WRT7 * WNDY / 365
           MOVE WINT TO BMF-INT
           ADD 1 TO N3
           MOVE BMF-EIN TO OR-EIN
           MOVE BMF-MFT TO OR-MFT
           MOVE BMF-TXPD TO OR-TXPD
           MOVE "O802" TO OR-COD
           MOVE "OVERPAYMENT INTEREST ALLOWED" TO OR-TXT
           MOVE WOVP TO OR-OVP
           MOVE WNDY TO OR-DAYS
           MOVE WINT TO OR-INT
           WRITE OIRPT-REC FROM ORPT.
       2100-X.
           EXIT.
