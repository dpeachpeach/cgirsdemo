       IDENTIFICATION DIVISION.
       PROGRAM-ID. ENTVAL.
      *****************************************************************
      *    BMF ENTITY VALIDATION - EIN PREFIX, NAME CONTROL, FRC      *
      *    STEP 010 OF THE NIGHTLY ENTITY RUN.                        *
      *    REV 03/91 PREFIX TABLE RELOAD PER RCC-4471                 *
      *****************************************************************
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ENTIN  ASSIGN TO "data/ENTMAST.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS1.
           SELECT ENTOT  ASSIGN TO "data/ENTVAL.dat"
               ORGANIZATION IS SEQUENTIAL
               FILE STATUS IS FS2.
           SELECT ERRPT  ASSIGN TO "data/ENTERR.rpt"
               ORGANIZATION IS LINE SEQUENTIAL
               FILE STATUS IS FS3.
       DATA DIVISION.
       FILE SECTION.
       FD  ENTIN
           RECORD CONTAINS 150 CHARACTERS.
       COPY ENTREC.
       FD  ENTOT
           RECORD CONTAINS 150 CHARACTERS.
       01  ENTOT-REC               PIC X(150).
       FD  ERRPT.
       01  ERRPT-REC               PIC X(120).
       WORKING-STORAGE SECTION.
       01  FS1                     PIC XX VALUE "00".
       01  FS2                     PIC XX VALUE "00".
       01  FS3                     PIC XX VALUE "00".
       01  EOFSW                   PIC X VALUE "N".
       01  R1                      PIC 9(6) VALUE ZERO.
       01  R2                      PIC 9(6) VALUE ZERO.
       01  R3                      PIC 9(6) VALUE ZERO.
       01  R4                      PIC 9(6) VALUE ZERO.
       01  IX                      PIC S9(4) COMP.
       01  WPFX                     PIC 9(2).
       01  WPSW                   PIC X.
       01  WNSW                    PIC X.
       01  E01                     PIC X(01).
      *
      *    CAMPUS ASSIGNED BMF PREFIXES.  SEE IRM 3.13.2 EXHIBIT.
      *
       01  PFXTAB.
           05  FILLER              PIC X(20) VALUE
               "10122026274546478182".
           05  FILLER              PIC X(20) VALUE
               "83848586878891929394".
           05  FILLER              PIC X(20) VALUE
               "95981113161735384344".
       01  PFXTABR REDEFINES PFXTAB.
           05  PFXENT              PIC 9(02) OCCURS 30.
       01  NC-PARM.
           05  NCP-NAME            PIC X(35).
           05  NCP-NCTL            PIC X(04).
           05  NCP-RC              PIC X(01).
           05  NCP-RSV             PIC X(08).
       01  ERRLIN.
           05  FILLER              PIC X(06) VALUE "ENTVAL".
           05  FILLER              PIC X(02) VALUE SPACES.
           05  EL-EIN              PIC 9(09).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  EL-COD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  EL-TXT              PIC X(40).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  EL-OLD              PIC X(04).
           05  FILLER              PIC X(02) VALUE SPACES.
           05  EL-NEW              PIC X(04).
           05  FILLER              PIC X(43) VALUE SPACES.
       PROCEDURE DIVISION.
       0000-MAIN.
           PERFORM 1000-INIT
           PERFORM 2000-PROC UNTIL EOFSW = "Y"
           PERFORM 9000-EOJ
           STOP RUN.
       1000-INIT.
           OPEN INPUT ENTIN OUTPUT ENTOT ERRPT
           IF FS1 NOT = "00"
               DISPLAY "ENTVAL OPEN FAIL ENTIN " FS1
               MOVE 16 TO RETURN-CODE
               STOP RUN
           END-IF.
       2000-PROC.
           READ ENTIN
               AT END
                   MOVE "Y" TO EOFSW
               NOT AT END
                   ADD 1 TO R1
                   PERFORM 2100-EDIT
                   WRITE ENTOT-REC FROM ENT-REC
                   ADD 1 TO R2
           END-READ.
       2100-EDIT.
           MOVE "N" TO WPSW
           MOVE "N" TO WNSW
           PERFORM 2200-PFX
           PERFORM 2300-NCTL THRU 2300-X
           PERFORM 2400-FRC.
       2200-PFX.
           MOVE ENT-EIN(1:2) TO WPFX
           PERFORM VARYING IX FROM 1 BY 1 UNTIL IX > 30
               IF PFXENT(IX) = WPFX
                   MOVE "Y" TO WPSW
                   MOVE 31 TO IX
               END-IF
           END-PERFORM
           IF WPSW = "N"
               MOVE ENT-EIN TO EL-EIN
               MOVE "E101" TO EL-COD
               MOVE "PREFIX NOT IN CAMPUS TABLE" TO EL-TXT
               MOVE SPACES TO EL-OLD
               MOVE SPACES TO EL-NEW
               WRITE ERRPT-REC FROM ERRLIN
               ADD 1 TO R3
           END-IF.
       2300-NCTL.
           MOVE ENT-NAME TO NCP-NAME
           MOVE SPACES TO NCP-NCTL
           CALL "NAMCTL" USING NC-PARM
           IF NCP-RC NOT = "0"
               MOVE ENT-EIN TO EL-EIN
               MOVE "E102" TO EL-COD
               MOVE "NAME CONTROL NOT DERIVABLE" TO EL-TXT
               MOVE ENT-NCTL TO EL-OLD
               MOVE SPACES TO EL-NEW
               WRITE ERRPT-REC FROM ERRLIN
               ADD 1 TO R3
               GO TO 2300-X
           END-IF
           IF NCP-NCTL NOT = ENT-NCTL
               MOVE ENT-EIN TO EL-EIN
               MOVE "E103" TO EL-COD
               MOVE "NAME CONTROL MISMATCH - CORRECTED" TO EL-TXT
               MOVE ENT-NCTL TO EL-OLD
               MOVE NCP-NCTL TO EL-NEW
               WRITE ERRPT-REC FROM ERRLIN
               ADD 1 TO R4
               MOVE NCP-NCTL TO ENT-NCTL
               MOVE "Y" TO WNSW
           END-IF.
       2300-X.
           EXIT.
       2400-FRC.
           IF ENT-EC = "F" AND ENT-I-940 = "1"
               MOVE ENT-EIN TO EL-EIN
               MOVE "E104" TO EL-COD
               MOVE "EC F INCOMPATIBLE WITH 940 FRC" TO EL-TXT
               MOVE SPACES TO EL-OLD
               MOVE SPACES TO EL-NEW
               WRITE ERRPT-REC FROM ERRLIN
               ADD 1 TO R3
               MOVE SPACE TO ENT-I-940
           END-IF
           IF ENT-FYM = ZERO
               MOVE 12 TO ENT-FYM
           END-IF.
       9000-EOJ.
           CLOSE ENTIN ENTOT ERRPT
           DISPLAY "ENTVAL  READ    " R1
           DISPLAY "ENTVAL  WRITTEN " R2
           DISPLAY "ENTVAL  ERRORS  " R3
           DISPLAY "ENTVAL  NC CORR " R4.
