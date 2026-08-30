       IDENTIFICATION DIVISION.
       PROGRAM-ID. DATECNV.
      *****************************************************************
      *    DATE UTILITY.  JULIAN / GREGORIAN AND BUSINESS DAY SHIFT   *
      *    UNDER IRC 7503.  CALLED BY THE NOTICE AND INTEREST STEPS.  *
      *    HOLIDAY TABLE PER IRM 25.6.1.6.18.                         *
      *****************************************************************
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  HTAB.
           05  FILLER              PIC X(24) VALUE
               "010104160619070411111225".
       01  HTABR REDEFINES HTAB.
           05  HOL                 PIC 9(04) OCCURS 6.
       01  W1                      PIC S9(4) COMP.
       01  WI                      PIC S9(9) COMP.
       01  WDOW                    PIC S9(4) COMP.
       01  WMD                     PIC 9(4).
       01  WG                      PIC 9(8).
       01  WSW                     PIC X.
       01  WGUARD                  PIC S9(4) COMP.
       LINKAGE SECTION.
       01  DV-PARM.
           05  DVP-FUNC            PIC X(01).
           05  DVP-GREG            PIC 9(08).
           05  DVP-JUL             PIC 9(07).
           05  DVP-DOW             PIC 9(01).
           05  DVP-RC              PIC X(01).
           05  DVP-RSV             PIC X(06).
       PROCEDURE DIVISION USING DV-PARM.
       0000-ENT.
           MOVE "0" TO DVP-RC
           EVALUATE DVP-FUNC
               WHEN "J"
                   PERFORM 1000-JUL THRU 1000-X
               WHEN "G"
                   PERFORM 2000-GRG THRU 2000-X
               WHEN "B"
                   PERFORM 3000-BUS THRU 3000-X
               WHEN OTHER
                   MOVE "8" TO DVP-RC
           END-EVALUATE
           GOBACK.
       1000-JUL.
           MOVE "J" TO DVP-FUNC
           CALL "DATCNV" USING DV-PARM(1:24)
           IF DVP-RC NOT = "0"
               GO TO 1000-X
           END-IF
           PERFORM 4000-DOW.
       1000-X.
           EXIT.
       2000-GRG.
           MOVE "G" TO DVP-FUNC
           CALL "DATCNV" USING DV-PARM(1:24)
           IF DVP-RC NOT = "0"
               GO TO 2000-X
           END-IF
           PERFORM 4000-DOW.
       2000-X.
           EXIT.
       3000-BUS.
           MOVE ZERO TO WGUARD
           MOVE "Y" TO WSW
           PERFORM UNTIL WSW = "N" OR WGUARD > 10
               ADD 1 TO WGUARD
               MOVE "N" TO WSW
               PERFORM 4000-DOW
               IF DVP-DOW = 6 OR DVP-DOW = 7
                   MOVE "Y" TO WSW
               END-IF
               MOVE DVP-GREG(5:4) TO WMD
               PERFORM VARYING W1 FROM 1 BY 1 UNTIL W1 > 6
                   IF HOL(W1) = WMD
                       MOVE "Y" TO WSW
                   END-IF
               END-PERFORM
               IF WSW = "Y"
                   COMPUTE WI =
                       FUNCTION INTEGER-OF-DATE(DVP-GREG) + 1
                   COMPUTE DVP-GREG = FUNCTION DATE-OF-INTEGER(WI)
               END-IF
           END-PERFORM
           MOVE "J" TO DVP-FUNC
           CALL "DATCNV" USING DV-PARM(1:24)
           PERFORM 4000-DOW.
       3000-X.
           EXIT.
       4000-DOW.
           COMPUTE WI = FUNCTION INTEGER-OF-DATE(DVP-GREG)
           COMPUTE WDOW = FUNCTION MOD(WI 7)
           IF WDOW = ZERO
               MOVE 7 TO WDOW
           END-IF
           MOVE WDOW TO DVP-DOW.
       END PROGRAM DATECNV.
