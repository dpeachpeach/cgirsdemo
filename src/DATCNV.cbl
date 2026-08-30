       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATCNV.
      *****************************************************************
      *    JULIAN / GREGORIAN CONVERSION.  COBOL SHIM FOR THE HLASM   *
      *    ROUTINE OF THE SAME NAME - SEE SRC/ASM/DATCNV.ASM.         *
      *    FUNCTION BYTE AT DISPLACEMENT 0 SELECTS DIRECTION.         *
      *****************************************************************
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  DTAB.
           05  FILLER              PIC X(36) VALUE
               "031028031030031030031031030031030031".
       01  DTABR REDEFINES DTAB.
           05  DTM                 PIC 9(03) OCCURS 12.
       01  K1                      PIC S9(4) COMP.
       01  KY                      PIC S9(4) COMP.
       01  KM                      PIC S9(4) COMP.
       01  KD                      PIC S9(4) COMP.
       01  KA                      PIC S9(4) COMP.
       01  KL                      PIC S9(4) COMP.
       01  KR                      PIC S9(4) COMP.
       LINKAGE SECTION.
       01  DC-PARM.
           05  DCP-FUNC            PIC X(01).
           05  DCP-GREG            PIC 9(08).
           05  DCP-JUL             PIC 9(07).
           05  DCP-RC              PIC X(01).
           05  DCP-RSV             PIC X(07).
       PROCEDURE DIVISION USING DC-PARM.
       0000-ENT.
           MOVE "0" TO DCP-RC
           IF DCP-FUNC = "J"
               PERFORM 1000-TOJUL THRU 1000-X
           ELSE
               IF DCP-FUNC = "G"
                   PERFORM 2000-TOGRG THRU 2000-X
               ELSE
                   MOVE "8" TO DCP-RC
               END-IF
           END-IF
           GOBACK.
       1000-TOJUL.
           MOVE DCP-GREG(1:4) TO KY
           MOVE DCP-GREG(5:2) TO KM
           MOVE DCP-GREG(7:2) TO KD
           IF KM < 1 OR KM > 12 OR KD < 1 OR KD > 31
               MOVE "8" TO DCP-RC
               GO TO 1000-X
           END-IF
           PERFORM 3000-LEAP
           MOVE ZERO TO KA
           PERFORM VARYING K1 FROM 1 BY 1 UNTIL K1 NOT < KM
               ADD DTM(K1) TO KA
               IF K1 = 2
                   ADD KL TO KA
               END-IF
           END-PERFORM
           ADD KD TO KA
           COMPUTE DCP-JUL = KY * 1000 + KA.
       1000-X.
           EXIT.
       2000-TOGRG.
           COMPUTE KY = DCP-JUL / 1000
           COMPUTE KA = DCP-JUL - (KY * 1000)
           PERFORM 3000-LEAP
           IF KA < 1 OR KA > (365 + KL)
               MOVE "8" TO DCP-RC
               GO TO 2000-X
           END-IF
           MOVE 1 TO KM
           PERFORM UNTIL KM > 12
               MOVE DTM(KM) TO KR
               IF KM = 2
                   ADD KL TO KR
               END-IF
               IF KA NOT > KR
                   GO TO 2000-BLD
               END-IF
               SUBTRACT KR FROM KA
               ADD 1 TO KM
           END-PERFORM.
       2000-BLD.
           COMPUTE DCP-GREG = KY * 10000 + KM * 100 + KA.
       2000-X.
           EXIT.
       3000-LEAP.
           MOVE ZERO TO KL
           COMPUTE KR = FUNCTION MOD(KY 4)
           IF KR = ZERO
               MOVE 1 TO KL
               COMPUTE KR = FUNCTION MOD(KY 100)
               IF KR = ZERO
                   MOVE ZERO TO KL
                   COMPUTE KR = FUNCTION MOD(KY 400)
                   IF KR = ZERO
                       MOVE 1 TO KL
                   END-IF
               END-IF
           END-IF.
       END PROGRAM DATCNV.
