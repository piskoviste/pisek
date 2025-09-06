import java.util.Scanner;

public class solve_all_ones {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int N = scanner.nextInt();

        for (int i = 0; i < N; i++) {
            System.out.print("1 ");
        }
        System.out.println();

        scanner.close();
    }
}
